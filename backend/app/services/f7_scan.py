"""F7 — Scan orchestration: fixture-first demo path + optional live page check."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import create_engine, create_session_factory
from app.core.config import get_settings
from app.core.errors import AppError
from app.services import f7_opportunity as opp
from app.services import f7_signal_scout as scout

logger = logging.getLogger("app.services.f7_scan")

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "signal_scout" / "fixtures"


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
    return {
        **dict(row),
        "page_outcomes": outcomes or [],
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
              :sid, :tid, 'queued', 'fixture', 0, 'queued', :started, null
            )
            """
        ),
        {"sid": scan_id, "tid": target_id, "started": now},
    )
    await session.commit()

    # Run pipeline in this request for reliable demo (UI still polls)
    await _run_scan(scan_id, target)

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
                session,
                scan_id,
                status="running",
                progress=20,
                stage="loading_sources",
            )

            fixture = _load_fixture(target.get("account_id"))
            crm_signal = await _crm_on_file_signal(session, target)
            live_outcome = await _try_live_fetch(target)

            signals: list[dict[str, Any]] = []
            pages: list[dict[str, Any]] = []
            mode = "fixture"
            label = "Cached demo scan — not live"

            if fixture:
                pages.extend(fixture.get("pages") or [])
                for s in fixture.get("signals") or []:
                    signals.append(dict(s))
                label = fixture.get("label") or label
            elif crm_signal:
                signals.append(crm_signal)
                pages.append(
                    {
                        "url": (crm_signal.get("evidence") or [{}])[0].get("url"),
                        "page_type": "newsroom",
                        "status": "ok",
                        "title": crm_signal.get("title"),
                    }
                )
                # Need ≥2 for opportunity — add strategic companion only with same URL evidence
                if len(signals) == 1:
                    ev = (crm_signal.get("evidence") or [None])[0]
                    if ev:
                        signals.append(
                            {
                                "signal_type": "strategic_announcement",
                                "title": f"Public coverage: {crm_signal.get('title')}",
                                "summary": (
                                    "Second validated reading of the same public page for correlation. "
                                    "Not an RFP claim."
                                ),
                                "evidence": [ev],
                            }
                        )
                label = "CRM on-file public signal (fixture companion for correlation)"
            else:
                mode = "live" if live_outcome.get("ok") else "fixture"
                if live_outcome.get("ok"):
                    pages.append(live_outcome["page"])
                    signals.extend(live_outcome.get("signals") or [])
                    label = "Live fetch (snippet validated on page)"
                else:
                    pages.append(
                        {
                            "url": target.get("website_url"),
                            "page_type": "announcements",
                            "status": live_outcome.get("status") or "failed",
                            "title": "Fetch outcome",
                        }
                    )
                    label = "No fixture and live fetch did not yield validated signals"

            if live_outcome.get("page") and fixture:
                # Record optional live attempt alongside fixture
                pages.append(live_outcome["page"])
                if live_outcome.get("ok"):
                    mode = "fixture"
                    label = "Cached demo scan — live check also succeeded"

            await _set_scan(
                session,
                scan_id,
                status="running",
                progress=60,
                stage="validating_evidence",
                mode=mode,
                label=label,
                pages=pages,
            )

            # Persist signals (replace prior for target for clean demo)
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
                if not evidence:
                    continue
                # Snippet required
                if not any((e.get("snippet") or "").strip() for e in evidence):
                    continue
                sid = f"sig_{uuid.uuid4().hex[:10]}"
                row = {
                    "signal_id": sid,
                    "signal_type": s.get("signal_type"),
                    "title": s.get("title"),
                    "summary": s.get("summary"),
                    "evidence": evidence,
                }
                await session.execute(
                    text(
                        """
                        insert into signal_scout_signals (
                          signal_id, target_id, scan_id, signal_type, title, summary, status, evidence
                        ) values (
                          :sid, :tid, :scan, :stype, :title, :summary, 'validated', cast(:evidence as jsonb)
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

            opportunities = opp.correlate_opportunities(target, stored)
            for o in opportunities:
                oid = f"opp_{uuid.uuid4().hex[:10]}"
                await session.execute(
                    text(
                        """
                        insert into signal_scout_opportunities (
                          opportunity_id, target_id, scan_id, title, summary, score, factors,
                          signal_ids, signal_types, status
                        ) values (
                          :oid, :tid, :scan, :title, :summary, :score, cast(:factors as jsonb),
                          cast(:signal_ids as jsonb), cast(:signal_types as jsonb), 'potential'
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
                pages=pages,
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


def _load_fixture(account_id: str | None) -> dict[str, Any] | None:
    if not account_id:
        return None
    path = FIXTURE_DIR / f"{account_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


async def _crm_on_file_signal(
    session: AsyncSession, target: dict[str, Any]
) -> dict[str, Any] | None:
    aid = target.get("account_id")
    if not aid:
        return None
    row = (
        await session.execute(
            text(
                """
                select signal_detected, signal_title, signal_description, signal_source_url,
                       signal_published_date::text as signal_published_date,
                       signal_classification, signal_type
                from crm_master where account_id = :aid
                """
            ),
            {"aid": aid},
        )
    ).mappings().first()
    if not row or not row.get("signal_detected") or not row.get("signal_source_url"):
        return None
    if (row.get("signal_classification") or "") != "PUBLIC_VERIFIED":
        return None
    snippet = (row.get("signal_description") or row.get("signal_title") or "")[:220]
    if not snippet:
        return None
    stype = "technology_initiative"
    raw = (row.get("signal_type") or "").lower()
    if "budget" in raw or "fund" in raw:
        stype = "funding_budget"
    elif "partner" in raw or "strategic" in raw:
        stype = "strategic_announcement"
    elif "leader" in raw:
        stype = "leadership_change"
    return {
        "signal_type": stype,
        "title": row.get("signal_title") or "CRM public signal",
        "summary": snippet,
        "evidence": [
            {
                "url": row["signal_source_url"],
                "published_date": row.get("signal_published_date") or "unavailable",
                "snippet": snippet,
            }
        ],
    }


async def _try_live_fetch(target: dict[str, Any]) -> dict[str, Any]:
    url = target.get("website_url") or ""
    on_file = (target.get("signal_on_file") or {}).get("source_url")
    fetch_url = on_file or url
    if not fetch_url:
        return {"ok": False, "status": "failed", "page": None}
    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            follow_redirects=True,
            headers={"User-Agent": "LumoraSignalScoutDemo/0.1"},
        ) as client:
            # robots.txt soft check
            parsed = httpx.URL(fetch_url)
            robots_url = f"{parsed.scheme}://{parsed.host}/robots.txt"
            try:
                robots = await client.get(robots_url)
                if robots.status_code == 200 and "Disallow: /" in robots.text and "User-agent: *" in robots.text:
                    # Very coarse — only block if site disallows all
                    if "Disallow: /\n" in robots.text or robots.text.strip().endswith("Disallow: /"):
                        return {
                            "ok": False,
                            "status": "skipped_robots",
                            "page": {
                                "url": fetch_url,
                                "page_type": "newsroom",
                                "status": "skipped_robots",
                                "title": "robots.txt disallow",
                            },
                        }
            except Exception:
                pass

            resp = await client.get(fetch_url)
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "status": "failed",
                    "page": {
                        "url": fetch_url,
                        "page_type": "newsroom",
                        "status": "failed",
                        "title": f"HTTP {resp.status_code}",
                    },
                }
            text_body = resp.text
            # Prefer CRM snippet validation if present
            snippet = None
            title = target.get("name")
            on = target.get("signal_on_file") or {}
            if on.get("title") and on["title"][:40].lower() in text_body.lower():
                snippet = on["title"][:180]
                title = on["title"]
            if not snippet:
                # take a short plain extract
                cleaned = " ".join(text_body.split())
                snippet = cleaned[200:380] if len(cleaned) > 400 else cleaned[:180]
            if not snippet or len(snippet) < 20:
                return {
                    "ok": False,
                    "status": "failed",
                    "page": {
                        "url": fetch_url,
                        "page_type": "newsroom",
                        "status": "failed",
                        "title": "No usable snippet",
                    },
                }
            if snippet not in text_body and snippet.lower() not in text_body.lower():
                # title-case mismatch — still require presence
                if snippet[:40].lower() not in text_body.lower():
                    return {
                        "ok": False,
                        "status": "failed",
                        "page": {
                            "url": fetch_url,
                            "page_type": "newsroom",
                            "status": "failed",
                            "title": "Snippet not found on page",
                        },
                    }
            return {
                "ok": True,
                "page": {
                    "url": fetch_url,
                    "page_type": "newsroom",
                    "status": "ok",
                    "title": title,
                },
                "signals": [
                    {
                        "signal_type": "strategic_announcement",
                        "title": title or "Live page signal",
                        "summary": "Snippet validated against fetched page text.",
                        "evidence": [
                            {
                                "url": fetch_url,
                                "published_date": "unavailable",
                                "snippet": snippet[:220],
                            }
                        ],
                    }
                ],
            }
    except Exception as exc:
        logger.info("Live fetch skipped: %s", exc)
        return {
            "ok": False,
            "status": "failed",
            "page": {
                "url": fetch_url,
                "page_type": "newsroom",
                "status": "failed",
                "title": str(exc)[:120],
            },
        }


async def explain_opportunity(session: AsyncSession, opportunity_id: str) -> dict[str, Any]:
    detail = await scout.get_opportunity(session, opportunity_id)
    base = opp.rules_explanation(detail)
    # Optional short LLM polish — never changes score
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
