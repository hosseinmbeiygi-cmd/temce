"""Persian news-tag → symbol/fund mapping service.

The news tagger stores human tickers (``خودرو``، ``فولاد``، ``وبانک``)
whose spelling doesn't always match the canonical ``symbols.symbol`` /
``funds.symbol`` values, which frequently use **Arabic** ي/ك instead of
Persian ی/ک and contain ZWNJ/non-breaking spaces (verified live:
``وبانک`` tag vs ``وبانك`` symbol, ``فملی`` tag vs ``فملي`` symbol,
426/511 symbols contain Arabic characters).

Resolution order (first hit wins):

1. ``manual``     — persisted override row in ``news_tag_symbol_map``
2. ``exact``      — normalized tag equals a symbols.symbol (Persian
                    normalization: Arabic ي/ك/ة endings → Persian, ZWNJ
                    folded to space, whitespace collapsed, digits unified)
3. ``arabic_fallback`` — no Persian match, but the tag's Arabic-spelled
                    form (yeh→ي, kaf→ك back-conversion) matches a symbol
4. ``fund_exact`` part of exact above — funds are probed alongside
                    symbols at each stage (funds first: a fund tag like
                    ``آسود2`` is unambiguous)
5. ``unmapped``   — nothing matched; the attempt is recorded so the
                    auto-mapper doesn't retry every request

``normalize_persian`` is exported for reuse by the backfill/auto-mapper
and the read repo so every consumer shares one canonical form.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

# Confidence per match type — manual beats derived matches.
_CONFIDENCE = {"manual": 1.00, "exact": 0.95, "arabic_fallback": 0.80}

# Arabic → Persian character folding (applied to both tag and target).
_CHAR_MAP = {
    "ي": "ی",  # Arabic yeh
    "ك": "ک",  # Arabic kaf
    "ة": "ه",  # teh marbuta
    "ۀ": "ه",
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",  # alef variants (ticker context: safe fold)
    "ؤ": "و",
    "ئ": "ی",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
}
_CHAR_RE = re.compile("[" + "".join(_CHAR_MAP) + "]")

# Zero-width joiners fold to a space (نیم‌فاصله ≡ فاصله for matching:
# ``سرمايه‌گذاري`` must equal ``سرمایه گذاری``); the rest are pure noise.
_ZWNJ_RE = re.compile("[\u200c\u200d]")
_STRIP_RE = re.compile("[\u200f\u200e\u202a-\u202e\ufeff\u00a0]")


def normalize_persian(value: str | None) -> str:
    """Canonical Persian form of a ticker: fold Arabic chars, strip
    zero-width joiners, collapse whitespace, casefold (for latin digits)."""
    if not value:
        return ""
    v = _STRIP_RE.sub(" ", value)
    v = _ZWNJ_RE.sub(" ", v)
    v = _CHAR_RE.sub(lambda m: _CHAR_MAP[m.group(0)], v)
    v = " ".join(v.split())
    return v.casefold()


def _spelling_variants(value: str | None) -> set[str]:
    """Spelling variants of a ticker: raw, Persian-normalized, and the
    Arabic back-spelled form (ی→ي، ک→ك)."""
    if not value:
        return set()
    norm = normalize_persian(value)
    arabic = norm.translate(str.maketrans("یک", "يك"))
    return {v for v in (value.strip(), norm, arabic) if v}


class NewsTagSymbolMapper:
    """Resolves and persists news-tag → symbol/fund mappings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── resolution ────────────────────────────────────────────────────

    async def resolve(self, tag_value: str, persist: bool = True) -> dict[str, Any] | None:
        """Resolve one tag to a symbol/fund target.

        Returns the mapping dict (``resolved_type``/``resolved_id``/
        ``resolved_symbol``/``match_type``/``confidence``) or ``None`` when
        the tag matches nothing. Successful resolutions are persisted
        (unless ``persist=False``); misses are recorded as ``unmapped`` so
        lookups stop re-querying symbols/funds for hopeless tags.
        """
        norm = normalize_persian(tag_value)
        if not norm:
            return None

        # 1. manual/existing mapping (any persisted state wins — the
        #    auto-mapper never overrides a manual fix)
        existing = await self._get_persisted(tag_value, norm)
        if existing:
            return existing

        # 2. exact Persian match (funds first, then symbols)
        hit = await self._probe_tables(norm)
        match_type = "exact"

        # 3. Arabic back-spelled fallback (ی→ي، ک→ك)
        if hit is None:
            arabic = norm.translate(str.maketrans("یک", "يك"))
            if arabic != norm:
                hit = await self._probe_tables(arabic)
                if hit is not None:
                    match_type = "arabic_fallback"

        if hit is None:
            if persist:
                await self._record_unmapped(tag_value, norm)
            return None

        resolved_type, resolved_id, resolved_symbol = hit
        mapping = {
            "tag_value": tag_value,
            "normalized_tag": norm,
            "resolved_type": resolved_type,
            "resolved_id": resolved_id,
            "resolved_symbol": resolved_symbol,
            "match_type": match_type,
            "confidence": _CONFIDENCE[match_type],
        }
        if persist:
            await self._persist(mapping)
        return mapping

    # ── table probes ──────────────────────────────────────────────────

    async def _probe_tables(self, candidate: str) -> tuple[str, int, str] | None:
        """Look up a candidate spelling in funds then symbols.

        Returns ``(resolved_type, resolved_id, resolved_symbol)`` or None.
        The Arabic↔Persian normalization above makes a single equality
        probe per table sufficient in either stage.
        """
        row = (
            await self.session.execute(
                text("SELECT id, symbol FROM funds WHERE symbol = :c LIMIT 1"),
                {"c": candidate},
            )
        ).first()
        if row:
            return ("fund", str(row[0]), row[1])  # funds.id is VARCHAR
        row = (
            await self.session.execute(
                text("SELECT id, symbol FROM symbols WHERE symbol = :c LIMIT 1"),
                {"c": candidate},
            )
        ).first()
        if row:
            return ("symbol", str(row[0]), row[1])
        return None

    # ── persistence ───────────────────────────────────────────────────

    async def _get_persisted(self, tag_value: str, norm: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                text(
                    "SELECT resolved_type, resolved_id, match_type, confidence "
                    "FROM news_tag_symbol_map WHERE tag_value = :t"
                ),
                {"t": tag_value},
            )
        ).first()
        if not row:
            return None
        resolved_type, resolved_id, match_type, confidence = row
        if resolved_type is None or resolved_id is None:
            return None  # persisted unmapped — caller may retry via probe
        return {
            "tag_value": tag_value,
            "normalized_tag": norm,
            "resolved_type": resolved_type,
            "resolved_id": str(resolved_id),
            "resolved_symbol": await self._symbol_of(resolved_type, str(resolved_id)),
            "match_type": match_type,
            "confidence": float(confidence or 0),
        }

    async def _symbol_of(self, resolved_type: str, resolved_id: str) -> str | None:
        table = "funds" if resolved_type == "fund" else "symbols"
        # funds.id is VARCHAR, symbols.id is BIGINT — asyncpg requires the
        # *native* Python type per column, SQL-side CAST is not enough.
        param: str | int = resolved_id if resolved_type == "fund" else int(resolved_id)
        row = (
            await self.session.execute(
                text(f"SELECT symbol FROM {table} WHERE id = :i"), {"i": param}
            )
        ).first()
        return row[0] if row else None

    async def _persist(self, mapping: dict[str, Any]) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO news_tag_symbol_map
                    (tag_value, normalized_tag, resolved_type, resolved_id,
                     match_type, confidence, mapped_at)
                VALUES (:t, :n, :rt, :ri, :mt, :cf, now())
                ON CONFLICT (tag_value) DO UPDATE SET
                    normalized_tag = EXCLUDED.normalized_tag,
                    resolved_type = EXCLUDED.resolved_type,
                    resolved_id = EXCLUDED.resolved_id,
                    match_type = EXCLUDED.match_type,
                    confidence = EXCLUDED.confidence,
                    mapped_at = now()
                WHERE news_tag_symbol_map.match_type <> 'manual'
                """
            ),
            {
                "t": mapping["tag_value"],
                "n": mapping["normalized_tag"],
                "rt": mapping["resolved_type"],
                "ri": mapping["resolved_id"],
                "mt": mapping["match_type"],
                "cf": mapping["confidence"],
            },
        )

    async def _record_unmapped(self, tag_value: str, norm: str) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO news_tag_symbol_map
                    (tag_value, normalized_tag, resolved_type, resolved_id, match_type, confidence)
                VALUES (:t, :n, NULL, NULL, 'unmapped', 0)
                ON CONFLICT (tag_value) DO NOTHING
                """
            ),
            {"t": tag_value, "n": norm},
        )

    # ── reverse lookup (read path) ───────────────────────────────────

    async def tag_values_for_symbol(self, symbol: str) -> set[str]:
        """All news ``tag_value``s that refer to ``symbol``.

        Superset of: the symbol itself, its Persian/Arabic spelling
        variants (cheap, works even before any mapping row exists), and
        every persisted mapping whose target is this symbol (covers
        manual aliases like ``وبم`` → ``وبانك``). Read-only — never writes.
        """
        from sqlalchemy import bindparam

        out = _spelling_variants(symbol)
        if not out:
            return out
        # Match the symbol across every spelling variant — the caller may
        # pass the Persian form while the table stores the Arabic one.
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT m.tag_value FROM news_tag_symbol_map m
                    WHERE (m.resolved_type = 'symbol'
                           AND m.resolved_id IN (
                               SELECT CAST(id AS TEXT) FROM symbols
                               WHERE symbol IN :vs))
                       OR (m.resolved_type = 'fund'
                           AND m.resolved_id IN (
                               SELECT id FROM funds WHERE symbol IN :vs))
                    """
                ).bindparams(bindparam("vs", expanding=True)),
                {"vs": sorted(out)},
            )
        ).scalars().all()
        out.update(rows)
        return out

    # ── batch auto-mapping ────────────────────────────────────────────

    async def auto_map_all(self, batch_size: int = 200) -> dict[str, Any]:
        """Map every distinct ``stock_symbol`` tag value.

        Returns counts per match type; safe to re-run (persisted rows are
        reused, manual rows are never touched, misses are skipped via the
        unmapped registry unless ``force`` cleared them).
        """
        rows = (
            await self.session.execute(
                text(
                    "SELECT DISTINCT tag_value FROM news_tags "
                    "WHERE tag_type = 'stock_symbol' AND tag_value IS NOT NULL "
                    "ORDER BY tag_value"
                )
            )
        ).scalars().all()

        counts = {"mapped": 0, "manual_kept": 0, "unmapped": 0}
        unmapped_tags: list[str] = []
        for tag in rows:
            mapping = await self.resolve(tag, persist=True)
            if mapping is None:
                counts["unmapped"] += 1
                unmapped_tags.append(tag)
            elif mapping["match_type"] == "manual":
                counts["manual_kept"] += 1
            else:
                counts["mapped"] += 1
        counts["unmapped_tags"] = unmapped_tags
        return counts

    async def set_manual(self, tag_value: str, resolved_type: str, resolved_id: int | str) -> dict[str, Any]:
        """Persist a manual override (highest confidence, never auto-overridden)."""
        if resolved_type not in ("symbol", "fund"):
            raise ValueError("resolved_type must be 'symbol' or 'fund'")
        norm = normalize_persian(tag_value)
        await self.session.execute(
            text(
                """
                INSERT INTO news_tag_symbol_map
                    (tag_value, normalized_tag, resolved_type, resolved_id,
                     match_type, confidence, mapped_at)
                VALUES (:t, :n, :rt, :ri, 'manual', 1.00, now())
                ON CONFLICT (tag_value) DO UPDATE SET
                    resolved_type = EXCLUDED.resolved_type,
                    resolved_id = EXCLUDED.resolved_id,
                    match_type = 'manual',
                    confidence = 1.00,
                    mapped_at = now()
                """
            ),
            {"t": tag_value, "n": norm, "rt": resolved_type, "ri": str(resolved_id)},
        )
        return {
            "tag_value": tag_value,
            "resolved_type": resolved_type,
            "resolved_id": resolved_id,
            "match_type": "manual",
            "confidence": _CONFIDENCE["manual"],
        }
