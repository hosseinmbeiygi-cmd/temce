"""Admin endpoints for the news tag → symbol/fund mapping table.

Implements the §20.7 roadmap item of the news module spec: view and
manually override the ``news_tag_symbol_map`` rows (migration 0059).
All routes sit behind the ``admin`` role (router-level ``_require_admin``)
and every mutation writes an ``audit_logs`` row (actor from the JWT
``sub`` claim) so tag fixes are traceable.

Routes:

* ``GET    /news-tag-map``          — paged view, optional search
* ``GET    /news-tag-map/stats``    — per-match_type counts
* ``POST   /news-tag-map/{tag}/manual`` — set/replace a manual override
* ``DELETE /news-tag-map/{tag}``    — drop the row (tag falls back to
  spelling variants only until the next auto-map)
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session, require_roles
from schemas.common.responses import ApiResponse
from services.news_tag_symbol_mapper import NewsTagSymbolMapper

router = APIRouter()


async def _audit(
    session: AsyncSession,
    action: str,
    entity_id: str,
    actor: str,
    changes: dict[str, Any] | None = None,
) -> None:
    """Append an audit_logs row for a mapping mutation.

    Best-effort on purpose: an audit failure must not roll back a
    successful mapping change... but both live in one transaction anyway,
    so instead of swallowing we let a broken audit table surface loudly —
    an admin change that is not traceable is worse than a failed request.
    """
    await session.execute(
        text(
            """
            INSERT INTO audit_logs (id, action, entity_type, entity_id, actor, changes, timestamp)
            VALUES (:id, :action, 'news_tag_symbol_map', :entity_id, :actor, :changes, now())
            """
        ),
        {
            "id": f"audit_{uuid.uuid4().hex[:40]}",
            "action": action,
            "entity_id": entity_id,
            "actor": actor,
            "changes": json.dumps(changes, ensure_ascii=False) if changes else None,
        },
    )


@router.get("")
async def list_mappings(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, description="substring filter on tag_value / resolved symbol"),
    match_type: str | None = Query(None, description="manual | exact | arabic_fallback | unmapped"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    """Paged view of the mapping table with resolved symbol names."""
    clauses: list[str] = []
    params: dict[str, Any] = {"lim": page_size, "off": (page - 1) * page_size}
    if q:
        clauses.append(
            "(m.tag_value ILIKE :q OR m.normalized_tag ILIKE :q "
            "OR COALESCE(f.symbol, s.symbol) ILIKE :q)"
        )
        params["q"] = f"%{q}%"
    if match_type:
        clauses.append("m.match_type = :mt")
        params["mt"] = match_type
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    rows = (
        await session.execute(
            text(
                f"""
                SELECT m.tag_value, m.normalized_tag, m.resolved_type, m.resolved_id,
                       COALESCE(f.symbol, s.symbol) AS resolved_symbol,
                       m.match_type, m.confidence, m.mapped_at
                FROM news_tag_symbol_map m
                LEFT JOIN funds f ON f.id = m.resolved_id AND m.resolved_type = 'fund'
                LEFT JOIN symbols s ON CAST(s.id AS TEXT) = m.resolved_id AND m.resolved_type = 'symbol'
                {where}
                ORDER BY m.match_type = 'manual' DESC, m.confidence DESC, m.tag_value
                LIMIT :lim OFFSET :off
                """
            ).bindparams(),
            params,
        )
    ).mappings().all()

    total = (
        await session.execute(
            text(
                f"""
                SELECT count(*) FROM news_tag_symbol_map m
                LEFT JOIN funds f ON f.id = m.resolved_id AND m.resolved_type = 'fund'
                LEFT JOIN symbols s ON CAST(s.id AS TEXT) = m.resolved_id AND m.resolved_type = 'symbol'
                {where}
                """
            ).bindparams(),
            params,
        )
    ).scalar_one()

    items = []
    for r in rows:
        row = dict(r)
        if row.get("confidence") is not None:
            row["confidence"] = float(row["confidence"])  # NUMERIC → JSON
        items.append(row)

    return ApiResponse(
        success=True,
        data={"items": items, "total": int(total), "page": page, "page_size": page_size},
    )


@router.get("/stats")
async def mapping_stats(session: AsyncSession = Depends(get_db_session)) -> ApiResponse[dict]:
    """Counts per match_type — the health signal of the auto-mapper."""
    rows = (
        await session.execute(
            text("SELECT match_type, count(*) AS c FROM news_tag_symbol_map GROUP BY match_type")
        )
    ).mappings().all()
    counts = {r["match_type"]: int(r["c"]) for r in rows}
    return ApiResponse(success=True, data={"counts": counts, "total": sum(counts.values())})


@router.post("/{tag}/manual")
async def set_manual_mapping(
    tag: str,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_db_session),
    user: dict = Depends(require_roles("admin")),
) -> ApiResponse[dict]:
    """Create/replace a manual override for ``tag``.

    Body: ``{"resolved_type": "symbol"|"fund", "resolved_id": <str|int>}``
    (``resolved_id`` as the symbols/funds PK value). Manual rows win over
    every auto mapping and are never overwritten by ``auto_map_all``.
    """
    resolved_type = str(body.get("resolved_type", ""))
    resolved_id = body.get("resolved_id")
    if resolved_type not in ("symbol", "fund"):
        raise HTTPException(status_code=422, detail="resolved_type must be 'symbol' or 'fund'")
    if resolved_id is None or str(resolved_id).strip() == "":
        raise HTTPException(status_code=422, detail="resolved_id is required")

    # validate the target exists before persisting anything — asyncpg
    # wants the native Python type per column (str for funds.id VARCHAR,
    # int for symbols.id BIGINT; SQL-side CAST is not enough).
    try:
        if resolved_type == "fund":
            target = (
                await session.execute(
                    text("SELECT symbol FROM funds WHERE id = :i"), {"i": str(resolved_id)}
                )
            ).first()
        else:
            target = (
                await session.execute(
                    text("SELECT symbol FROM symbols WHERE id = :i"),
                    {"i": int(resolved_id)},
                )
            ).first()
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="resolved_id must be an integer for symbols") from None
    if not target:
        raise HTTPException(status_code=404, detail=f"{resolved_type} id={resolved_id} not found")

    actor = str(user.get("sub") or "admin")
    mapper = NewsTagSymbolMapper(session)
    mapping = await mapper.set_manual(tag, resolved_type, str(resolved_id))
    await _audit(
        session,
        action="news_tag_map.manual_set",
        entity_id=tag,
        actor=actor,
        changes={
            "resolved_type": resolved_type,
            "resolved_id": str(resolved_id),
            "resolved_symbol": target[0],
        },
    )
    # Commit before responding: the global get_session teardown commits
    # after the response is sent, which lets an immediate follow-up read
    # (admin UI list / verify) race the commit and miss the row.
    await session.commit()
    return ApiResponse(success=True, data=mapping, message=f"manual override set by {actor}")


@router.delete("/{tag}")
async def delete_mapping(
    tag: str,
    session: AsyncSession = Depends(get_db_session),
    user: dict = Depends(require_roles("admin")),
) -> ApiResponse[dict]:
    """Remove the mapping row for ``tag`` (read path falls back to pure
    spelling variants; the next ``auto_map_all`` may recreate an auto row)."""
    existing = (
        await session.execute(
            text("SELECT match_type FROM news_tag_symbol_map WHERE tag_value = :t"),
            {"t": tag},
        )
    ).first()
    if not existing:
        raise HTTPException(status_code=404, detail=f"no mapping for tag {tag!r}")

    await session.execute(
        text("DELETE FROM news_tag_symbol_map WHERE tag_value = :t"), {"t": tag}
    )
    await _audit(
        session,
        action="news_tag_map.delete",
        entity_id=tag,
        actor=str(user.get("sub") or "admin"),
        changes={"previous_match_type": existing[0]},
    )
    # Same as set_manual: durable before the response, no read race.
    await session.commit()
    return ApiResponse(success=True, data={"tag_value": tag, "deleted": True})


@router.get("/{tag}/verify")
async def verify_tag(
    tag: str,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    """Dry-resolve one tag (never persists) — for checking an alias
    before committing a manual override."""
    mapper = NewsTagSymbolMapper(session)
    mapping = await mapper.resolve(tag, persist=False)
    return ApiResponse(success=True, data={"tag_value": tag, "resolved": mapping})
