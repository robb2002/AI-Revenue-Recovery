"""F7 — Scan: homepage discover → validate → AI extract → correlate → rules score.

Live discovery from the target website_url. Discovered pages are stored in
signal_scout_pages (linked to the university target) — no JSON fixture files.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.errors import AppError
from app.services import f7_discovery as discovery
from app.services import f7_opportunity as opp
from app.services import f7_page_validate as pages
from app.services import f7_signal_extract as extract
from app.services import f7_signal_scout as scout

logger = logging.getLogger("app.services.f7_scan")


class ScanInProgressError(AppError):
    status_code = 409
    code = "SCAN_IN_PROGRESS"
    message = "A scan is already running for this target."


async def get_scan(session: AsyncSession, scan_id: str) -> dict[str, Any]:
    await scout.ensure_f7_tables(session)
    row = (
        await session.execute(
            text(
                """
                select scan_id, target_id, status, mode, progress_pct, stage, page_outcomes,
                       error_summary, signal_count, opportunity_count, started_at, finished_at, label
                from signal_scout_scans where scan_id = :sid
                """
            ),
            {"sid": scan_id},
        )
    ).mappings().first()
    if not row:
        from app.core.errors import NotFoundError

        raise NotFoundError("scan")
    outcomes = row["page_outcomes"]
    if isinstance(outcomes, str):
        outcomes = json.loads(outcomes)
    normalized = []
    for p in outcomes or []:
        item = dict(p)
        if "page_category" not in item and item.get("page_type"):
            item["page_category"] = _legacy_page_type(item["page_type"])
        normalized.append(item)
    return {
        **dict(row),
        "page_outcomes": normalized,
        "started_at": row["started_at"].isoformat() if row.get("started_at") else None,
        "finished_at": row["finished_at"].isoformat() if row.get("finished_at") else None,
    }


async def start_scan(session: AsyncSession, target_id: str) -> dict[str, Any]:
    await scout.ensure_f7_tables(session)
    target = await scout.get_target(session, target_id)
    running = await session.scalar(
        text(
            """
            select scan_id from signal_scout_scans
            where target_id = :tid and status in ('queued','running')
            limit 1
            """
        ),
        {"tid": target_id},
    )
    if running:
        raise ScanInProgressError()

    scan_id = f"scan_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    await session.execute(
        text(
            """
            insert into signal_scout_scans (
              scan_id, target_id, status, mode, progress_pct, stage, started_at, label
            ) values (
              :sid, :tid, 'queued', 'live', 0, 'queued', :started, null
            )
            """
        ),
        {"sid": scan_id, "tid": target_id, "started": now},
    )
    await session.commit()
    # Background so the UI can poll stages (detect → validate → extract → correlate → score)
    asyncio.create_task(_run_scan(scan_id, dict(target)))
    return {
        "scan_id": scan_id,
        "target_id": target_id,
        "status": "queued",
        "message": "Scan started. Poll GET /signal-scout/scans/{scan_id}.",
    }


async def _run_scan(scan_id: str, target: dict[str, Any]) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    async with factory() as session:
        try:
            await _set_scan(
                session, scan_id, status="running", progress=10, stage="resolve_hubs"
            )

            website = target.get("website_url") or ""
            page_outcomes: list[dict[str, Any]] = []
            signals: list[dict[str, Any]] = []
            mode = "live"
            label = "Live homepage discovery"

            async with httpx.AsyncClient(
                timeout=12.0,
                follow_redirects=True,
                headers={"User-Agent": pages.USER_AGENT},
            ) as client:
                fetched, outcomes, disc_label = await discovery.discover_and_fetch_pages(
                    organization_name=target.get("name") or "Institution",
                    website_url=website,
                    client=client,
                )
                page_outcomes = outcomes
                label = disc_label.replace("_", " ")

                await _set_scan(
                    session,
                    scan_id,
                    status="running",
                    progress=40,
                    stage="validate_pages",
                    pages=page_outcomes,
                    mode="live",
                    label=label,
                )

                await _set_scan(
                    session,
                    scan_id,
                    status="running",
                    progress=55,
                    stage="extract",
                    pages=page_outcomes,
                )

                if fetched:
                    pages_data = [
                        {
                            "url": p.final_url,
                            "title": p.title,
                            "text": p.text,
                            "page_category": p.page_category,
                        }
                        for p in fetched
                    ]
                    signals = await extract.extract_signals_from_pages(
                        organization_name=target.get("name") or "Institution",
                        pages_data=pages_data,
                    )
                    await _set_scan(
                        session,
                        scan_id,
                        status="running",
                        progress=65,
                        stage="extract",
                        pages=page_outcomes,
                        signal_count=len(signals),
                        mode="live",
                        label=label,
                    )

            await _set_scan(
                session,
                scan_id,
                status="running",
                progress=70,
                stage="validate_evidence",
                pages=page_outcomes,
                signal_count=len(signals),
            )

            # Persist discovered pages on this university target (DB, not JSON files)
            await scout.upsert_target_pages(
                session,
                target_id=target["target_id"],
                account_id=target.get("account_id"),
                scan_id=scan_id,
                page_outcomes=page_outcomes,
            )

            await session.execute(
                text("delete from signal_scout_signals where target_id = :tid"),
                {"tid": target["target_id"]},
            )
            await session.execute(
                text("delete from signal_scout_opportunities where target_id = :tid"),
                {"tid": target["target_id"]},
            )

            stored: list[dict[str, Any]] = []
            for s in signals:
                evidence = s.get("evidence") or []
                if not evidence or not any((e.get("snippet") or "").strip() for e in evidence):
                    continue
                stype = s.get("signal_type")
                if stype not in pages.SIGNAL_TYPES:
                    continue
                sid = f"sig_{uuid.uuid4().hex[:10]}"
                row = {
                    "signal_id": sid,
                    "signal_type": stype,
                    "title": s.get("title"),
                    "summary": s.get("summary"),
                    "evidence": evidence,
                }
                await session.execute(
                    text(
                        """
                        insert into signal_scout_signals (
                          signal_id, target_id, scan_id, signal_type, title, summary,
                          status, evidence
                        ) values (
                          :sid, :tid, :scan, :stype, :title, :summary,
                          'validated', cast(:evidence as jsonb)
                        )
                        """
                    ),
                    {
                        "sid": sid,
                        "tid": target["target_id"],
                        "scan": scan_id,
                        "stype": row["signal_type"],
                        "title": row["title"],
                        "summary": row["summary"],
                        "evidence": json.dumps(evidence),
                    },
                )
                stored.append(row)

            await _set_scan(
                session,
                scan_id,
                status="running",
                progress=85,
                stage="correlate",
                pages=page_outcomes,
                signal_count=len(stored),
            )

            opportunities = opp.correlate_opportunities(target, stored)
            await _set_scan(
                session,
                scan_id,
                status="running",
                progress=95,
                stage="correlate",
                pages=page_outcomes,
                signal_count=len(stored),
                opportunity_count=len(opportunities),
            )
            for o in opportunities:
                oid = f"opp_{uuid.uuid4().hex[:10]}"
                await session.execute(
                    text(
                        """
                        insert into signal_scout_opportunities (
                          opportunity_id, target_id, scan_id, title, summary, score,
                          factors, signal_ids, signal_types, status
                        ) values (
                          :oid, :tid, :scan, :title, :summary, :score,
                          cast(:factors as jsonb), cast(:signal_ids as jsonb),
                          cast(:signal_types as jsonb), 'potential'
                        )
                        """
                    ),
                    {
                        "oid": oid,
                        "tid": target["target_id"],
                        "scan": scan_id,
                        "title": o["title"],
                        "summary": o["summary"],
                        "score": o["score"],
                        "factors": json.dumps(o["factors"]),
                        "signal_ids": json.dumps(o["signal_ids"]),
                        "signal_types": json.dumps(o["signal_types"]),
                    },
                )

            now = datetime.now(timezone.utc)
            await session.execute(
                text(
                    """
                    update signal_scout_targets
                    set last_scanned_at = :ts
                    where target_id = :tid
                    """
                ),
                {"ts": now, "tid": target["target_id"]},
            )
            await _set_scan(
                session,
                scan_id,
                status="completed",
                progress=100,
                stage="completed",
                mode=mode,
                label=label,
                pages=page_outcomes,
                signal_count=len(stored),
                opportunity_count=len(opportunities),
                finished=now,
            )
            await session.commit()
        except Exception as exc:
            logger.exception("Scan failed %s", scan_id)
            await _set_scan(
                session,
                scan_id,
                status="failed",
                progress=100,
                stage="failed",
                error=str(exc)[:400],
                finished=datetime.now(timezone.utc),
            )
            await session.commit()


async def _set_scan(
    session: AsyncSession,
    scan_id: str,
    *,
    status: str,
    progress: int,
    stage: str,
    mode: str | None = None,
    label: str | None = None,
    pages: list | None = None,
    signal_count: int | None = None,
    opportunity_count: int | None = None,
    error: str | None = None,
    finished: datetime | None = None,
) -> None:
    await session.execute(
        text(
            """
            update signal_scout_scans
            set status = :status,
                progress_pct = :progress,
                stage = :stage,
                mode = coalesce(:mode, mode),
                label = coalesce(:label, label),
                page_outcomes = coalesce(cast(:pages as jsonb), page_outcomes),
                signal_count = coalesce(:signal_count, signal_count),
                opportunity_count = coalesce(:opportunity_count, opportunity_count),
                error_summary = coalesce(:error, error_summary),
                finished_at = coalesce(:finished, finished_at)
            where scan_id = :sid
            """
        ),
        {
            "status": status,
            "progress": progress,
            "stage": stage,
            "mode": mode,
            "label": label,
            "pages": json.dumps(pages) if pages is not None else None,
            "signal_count": signal_count,
            "opportunity_count": opportunity_count,
            "error": error,
            "finished": finished,
            "sid": scan_id,
        },
    )
    await session.commit()


def _legacy_page_type(page_type: str) -> str:
    mapping = {
        "newsroom": "news",
        "announcements": "news",
        "leadership": "leadership",
        "budget": "funding",
        "board_minutes": "funding",
    }
    return mapping.get(page_type, page_type if page_type in pages.PAGE_HUB_CATEGORIES else "news")


async def explain_opportunity(session: AsyncSession, opportunity_id: str) -> dict[str, Any]:
    detail = await scout.get_opportunity(session, opportunity_id)
    base = opp.rules_explanation(detail)
    try:
        from app.ai.azure_openai import AzureChatClient

        client = AzureChatClient()
        if client.configured:
            result = await client.chat_json(
                system=(
                    "Explain a rules-based potential opportunity score. Return JSON "
                    '{"interpretation":"...","recommended_action":"..."}. '
                    "Do not change the score. Never say an RFP will happen or a deal will close."
                ),
                user=json.dumps(
                    {
                        "score": detail.get("score"),
                        "factors": detail.get("factors"),
                        "title": detail.get("title"),
                    }
                ),
                temperature=0.2,
                timeout_seconds=10.0,
            )
            if result:
                if result.get("interpretation"):
                    base["interpretation"] = {"text": str(result["interpretation"])}
                if result.get("recommended_action"):
                    base["recommended_action"] = {"text": str(result["recommended_action"])}
                base["source"] = "azure_openai"
    except Exception:
        logger.exception("Explain failed; returning rules explanation")
    await session.execute(
        text(
            """
            update signal_scout_opportunities
            set explanation = cast(:exp as jsonb)
            where opportunity_id = :oid
            """
        ),
        {"exp": json.dumps(base), "oid": opportunity_id},
    )
    await session.commit()
    return {**detail, "explanation": base}
