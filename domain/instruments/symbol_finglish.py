"""Finglish (Persian → Latin) symbol matching — pure domain logic, no DB.

Extracted from ``services/symbol_catalog.py`` so ``repositories`` can use
Finglish matching without importing the services layer (ADR-0001, Phase 1:
repository layering fix). The catalog itself stays in services and is
injected; this module owns only transliteration/matching logic.

 ponytail: ceiling = matching against the static catalog. When the catalog
 becomes DB-driven (Phase 2 read model), inject a callable instead of a list.
"""

from __future__ import annotations

import re

# ── Finglish transliteration (Persian → Latin) ─────────────────
# Lets the search find a symbol by its Latin spelling, e.g. ``folad``
# matches ``فولاد`` and ``zafaran`` matches ``زعفران``.
#
# Each Persian letter maps to its possible Finglish renderings. The first
# entry is the most common one; all are tried so common variations work
# (``و`` as o/u/v/w, ``ی`` as y/i, ``ع`` as silent a/e/gh, ...).
_FA_CANDIDATES: dict[str, tuple[str, ...]] = {
    "آ": ("a",),
    "ا": ("a",),
    "أ": ("a",),
    "إ": ("a",),
    "ب": ("b",),
    "پ": ("p",),
    "ت": ("t",),
    "ث": ("s", "th"),
    "ج": ("j",),
    "چ": ("ch", "c", "j"),
    "ح": ("h",),
    "خ": ("kh", "x", "h"),
    "د": ("d",),
    "ذ": ("z",),
    "ر": ("r",),
    "ز": ("z",),
    "ژ": ("zh", "j", "z"),
    "س": ("s",),
    "ش": ("sh", "s", "ch"),
    "ص": ("s",),
    "ض": ("z", "d"),
    "ط": ("t",),
    "ظ": ("z",),
    "ع": ("a", "e", "gh"),  # short vowels already injected by _SHORT_VOWEL
    "غ": ("gh", "g"),
    "ف": ("f",),
    "ق": ("gh", "g", "q"),
    "ک": ("k", "c"),
    "ك": ("k", "c"),
    "گ": ("g", "gh"),
    "ل": ("l",),
    "م": ("m",),
    "ن": ("n",),
    "و": ("o", "u", "v", "w"),
    "ه": ("h",),
    "ی": ("y", "i"),
    "ي": ("y", "i"),
    "ئ": ("y", "i", "e"),
    "ة": ("h", "t"),
    "۰": ("0",),
    "۱": ("1",),
    "۲": ("2",),
    "۳": ("3",),
    "۴": ("4",),
    "۵": ("5",),
    "۶": ("6",),
    "۷": ("7",),
    "۸": ("8",),
    "۹": ("9",),
}

# Short vowels are not written in Persian (فتحه/کسره/ضمه), so Finglish
# queries may insert them — ``tala`` for طلا, ``foolad`` for فولاد. This
# fragment is allowed (up to two) between every pair of transliterated
# letters to tolerate those insertions.
_SHORT_VOWEL = r"(?:[aeiouy]{0,2})"


# Collapse repeated letters (``foolad`` → ``folad``) so double-vowel
# misspellings still match.
_REPEAT_RE = re.compile(r"(.)\1+")


def _collapse_repeats(text: str) -> str:
    return _REPEAT_RE.sub(r"\1", text)


def _word_regex(word: str) -> str | None:
    """Build a regex matching any prefix of the word's Finglish spelling.

    Each Persian letter becomes an alternation of its possible Latin
    renderings; short vowels are allowed between letters and every group
    after the first is optional, so ``tala`` matches ``طلای`` and
    ``folad``/``foolad`` both match ``فولاد``. Returns ``None`` for empty
    words.
    """
    groups: list[str] = []
    for ch in word:
        if ch == "\u200c":  # ZWNJ (نیم‌فاصله) — invisible, skip
            continue
        candidates = _FA_CANDIDATES.get(ch)
        if candidates is not None:
            groups.append("(?:" + "|".join(re.escape(c) for c in candidates) + ")")
        elif ch.isascii():
            groups.append(re.escape(ch.lower()))
        else:
            groups.append(re.escape(ch))
    if not groups:
        return None
    # Chain the groups from the end so every group after the first is
    # optional — the query may be any prefix of the transliteration.
    pattern = groups[-1]
    for group in reversed(groups[:-1]):
        pattern = group + _SHORT_VOWEL + "(?:" + pattern + ")?"
    return pattern


def _build_translit_regexes(catalog: list[dict[str, str]]) -> list[list[str]]:
    """Precompute a Finglish regex per Persian word of every catalog entry.

    Pure-ASCII words are skipped: the direct substring match already covers
    Latin symbols/names and avoids loose regex matches for them.
    """
    out: list[list[str]] = []
    for item in catalog:
        patterns: list[str] = []
        for text in (item.get("symbol", ""), item.get("name", "")):
            for word in text.split():
                if word.isascii():
                    continue  # pure ASCII → handled by direct match
                pattern = _word_regex(word)
                if pattern:
                    patterns.append(pattern)
        out.append(patterns)
    return out


# Built once per injected catalog (see ``FinglishIndex``).


def finglish_matches(
    catalog: list[dict[str, str]],
    translit_regexes: list[list[str]],
    query: str,
    limit: int,
) -> list[dict[str, str]]:
    """Case-insensitive substring + Finglish search over a static catalog.

    Persian names/symbols are also matched by their Finglish (Latin)
    transliteration — e.g. ``folad`` finds ``فولاد`` and ``zafaran`` finds
    ``زعفران``. Repeated-letter misspellings (``foolad``) are tolerated.
    Returns ``{symbol, name, sector}`` dicts ordered by catalog order.
    """
    q = (query or "").strip().lower()
    if not q:
        return []
    limit = max(1, min(int(limit), 200))

    # Finglish matching only makes sense for Latin queries; Persian input is
    # already covered by the direct substring checks above.
    q_collapsed = _collapse_repeats(q) if q.isascii() else ""

    matches: list[dict[str, str]] = []
    for idx, item in enumerate(catalog):
        if (
            q in item["symbol"].lower()
            or q in item["name"].lower()
            or (
                q_collapsed
                # ``re.match`` anchors at the start of the query → the Latin
                # query must be a prefix of a transliteration (autocomplete
                # semantics). ``re.search`` would match a stray middle letter.
                and any(re.match(pattern, q_collapsed) for pattern in translit_regexes[idx])
            )
        ):
            matches.append(item)
            if len(matches) >= limit:
                break
    return matches


def finglish_symbol_candidates(
    catalog: list[dict[str, str]],
    translit_regexes: list[list[str]],
    query: str,
    limit: int = 50,
) -> list[str]:
    """Return Persian symbols whose Finglish spelling matches a Latin query.

    Used by DB-backed search (``instruments/search``, ``watchlist/search``)
    so a query like ``folad`` can also find the Persian symbol ``فولاد``
    that lives in PostgreSQL. Only non-ASCII (Persian) symbols are
    returned — Latin symbols already match via ``ILIKE``.

    Returns an empty list for empty or Persian queries, so callers can keep
    their plain substring behaviour unchanged in that case.
    """
    q = (query or "").strip()
    if not q or not q.isascii():
        return []
    # Scan the whole catalog first, then filter — otherwise Latin symbols
    # filling the limit would silently drop valid Persian candidates.
    results = finglish_matches(catalog, translit_regexes, q, limit=200)
    persian = [item["symbol"] for item in results if not item["symbol"].isascii()]
    return persian[: max(1, min(int(limit), 200))]
