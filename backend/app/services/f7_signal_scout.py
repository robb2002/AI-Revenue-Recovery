"""F7 — Signal Scout targets: search CRM, add target, assemble cards."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError

_tables_ready = False

URL_RE = re.compile(r"^https://", re.I)


class InvalidUrlError(AppError):
    status_code = 422
    code = "INVALID_URL"
    message = "Website URL must be HTTPS and look like an official institution host."


class ValidationAppError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "The request is not valid."


async def ensure_f7_tables(session: AsyncSession) -> None:
    global _tables_ready
    if _tables_ready:
        return
    await session.execute(
        text(
            """
            create table if not exists signal_scout_targets (
              target_id text primary key,
              account_id text,
              name text not null,
              website_url text not null,
              source text not null,
              last_scanned_at timestamptz,
              created_at timestamptz default now()
            )
            """
        )
    )
    await session.execute(
        text(
            """
            create table if not exists signal_scout_scans (
              scan_id text primary key,
              target_id text not null references signal_scout_targets(target_id),
              status text not null,
              mode text not null default 'fixture',
              progress_pct int default 0,
              stage text,
              page_outcomes jsonb default '[]'::jsonb,
              error_summary text,
              signal_count int default 0,
              opportunity_count int default 0,
              started_at timestamptz,
              finished_at timestamptz,
              label text
            )
            """
        )
    )
    await session.execute(
        text(
            """
            create table if not exists signal_scout_signals (
              signal_id text primary key,
              target_id text not null,
              scan_id text not null,
              signal_type text not null,
              title text not null,
              summary text,
              status text not null default 'validated',
              evidence jsonb not null default '[]'::jsonb,
              created_at timestamptz default now()
            )
            """
        )
    )
    await session.execute(
        text(
            """
            create table if not exists signal_scout_opportunities (
              opportunity_id text primary key,
              target_id text not null,
              scan_id text not null,
              title text not null,
              summary text,
              score int not null,
              factors jsonb not null default '[]'::jsonb,
              signal_ids jsonb not null default '[]'::jsonb,
              signal_types jsonb not null default '[]'::jsonb,
              status text not null default 'potential',
              explanation jsonb,
              created_at timestamptz default now()
            )
            """
        )
    )
    await session.commit()
    _tables_ready = True


def _validate_website(url: str) -> str:
    u = (url or "").strip()
    if not URL_RE.match(u):
        raise InvalidUrlError("Only HTTPS URLs are accepted.")
    host = (urlparse(u).hostname or "").lower()
    if not host or host in {"bit.ly", "t.co", "tinyurl.com", "goo.gl"}:
        raise InvalidUrlError("Link shorteners and empty hosts are not allowed.")
    # Prefer .edu / known institution-ish hosts; allow .gov and university news hosts
    ok = (
        host.endswith(".edu")
        or host.endswith(".ac.uk")
        or "university" in host
        or "college" in host
        or host.endswith(".gov")
        or host in {"www.calstate.edu", "news.asu.edu", "news.osu.edu", "www.sdsu.edu", "www.asu.edu", "www.osu.edu"}
    )
    if not ok and not any(x in host for x in (".edu", "university", "college", "school")):
        raise InvalidUrlError(
            "MVP allows official institution hosts (prefer .edu / university domains)."
        )
    return u.rstrip("/")


async def search_targets(session: AsyncSession, q: str, *, limit: int = 20) -> dict[str, Any]:
    await ensure_f7_tables(session)
    query = (q or "").strip()
    crm: list[dict[str, Any]] = []
    if query:
        rows = (
            await session.execute(
                text(
                    """
                    select account_id, account_name, deal_status, recovery_eligibility,
                           website, signal_source_url, signal_detected, signal_title,
                           signal_classification
                    from crm_master
                    where account_name ilike :q or account_id ilike :q
                    order by
                      case when signal_classification = 'PUBLIC_VERIFIED' then 0 else 1 end,
                      account_name
                    limit :limit
                    """
                ),
                {"q": f"%{query}%", "limit": limit},
            )
        ).mappings().all()
        for r in rows:
            crm.append(
                {
                    "account_id": r["account_id"],
                    "name": r["account_name"],
                    "deal_status": r["deal_status"],
                    "recovery_eligibility": r["recovery_eligibility"],
                    "website_url": r.get("website") or r.get("signal_source_url"),
                    "signal_on_file": bool(r.get("signal_detected")),
                    "signal_title": r.get("signal_title"),
                    "signal_classification": r.get("signal_classification"),
                    "source": "crm",
                }
            )

    manual = (
        await session.execute(
            text(
                """
                select target_id, account_id, name, website_url, source, last_scanned_at
                from signal_scout_targets
                where source = 'manual'
                  and (:q = '' or name ilike :like)
                order by created_at desc
                limit :limit
                """
            ),
            {"q": query, "like": f"%{query}%", "limit": limit},
        )
    ).mappings().all()

    recent = (
        await session.execute(
            text(
                """
                select target_id, account_id, name, website_url, source, last_scanned_at
                from signal_scout_targets
                order by coalesce(last_scanned_at, created_at) desc
                limit 8
                """
            )
        )
    ).mappings().all()

    return {
        "crm": crm,
        "manual": [dict(m) for m in manual],
        "recent": [
            {
                **dict(r),
                "last_scanned_at": r["last_scanned_at"].isoformat()
                if r.get("last_scanned_at")
                else None,
            }
            for r in recent
        ],
        "notice": (
            "Signal Scout finds public pre-RFP changes with citations. "
            "It does not predict RFPs or create pipeline automatically."
        ),
    }


async def create_target(
    session: AsyncSession,
    *,
    account_id: str | None = None,
    name: str | None = None,
    website_url: str | None = None,
) -> dict[str, Any]:
    await ensure_f7_tables(session)

    if account_id:
        row = (
            await session.execute(
                text(
                    """
                    select account_id, account_name, website, signal_source_url,
                           deal_status, recovery_eligibility, signal_detected,
                           signal_title, signal_classification
                    from crm_master where account_id = :aid
                    """
                ),
                {"aid": account_id},
            )
        ).mappings().first()
        if not row:
            raise NotFoundError("account")
        existing = await session.scalar(
            text(
                "select target_id from signal_scout_targets where account_id = :aid limit 1"
            ),
            {"aid": account_id},
        )
        if existing:
            return await get_target(session, existing)

        raw_url = row.get("website") or row.get("signal_source_url")
        if not raw_url:
            raise InvalidUrlError("No website or signal URL on this CRM account.")
        raw_url = str(raw_url).strip()
        if raw_url.startswith("http://"):
            raw_url = "https://" + raw_url[len("http://") :]
        if not raw_url.startswith("https://"):
            raw_url = "https://" + raw_url.lstrip("/")
        # Prefer homepage for card when signal URL is an article
        card_url = row.get("website") or raw_url
        card_url = str(card_url).strip()
        if card_url.startswith("http://"):
            card_url = "https://" + card_url[len("http://") :]
        if not card_url.startswith("https://"):
            card_url = "https://" + card_url.lstrip("/")
        url = _validate_website(card_url)
        tid = f"tgt_{account_id.lower()}"
        await session.execute(
            text(
                """
                insert into signal_scout_targets (target_id, account_id, name, website_url, source)
                values (:tid, :aid, :name, :url, 'crm')
                on conflict (target_id) do update
                  set name = excluded.name, website_url = excluded.website_url
                """
            ),
            {
                "tid": tid,
                "aid": account_id,
                "name": row["account_name"],
                "url": url,
            },
        )
        await session.commit()
        return await get_target(session, tid)

    if not name or not website_url:
        raise ValidationAppError("Provide account_id or both name and website_url.")
    url = _validate_website(website_url)
    tid = f"tgt_manual_{uuid.uuid4().hex[:10]}"
    await session.execute(
        text(
            """
            insert into signal_scout_targets (target_id, account_id, name, website_url, source)
            values (:tid, null, :name, :url, 'manual')
            """
        ),
        {"tid": tid, "name": name.strip(), "url": url},
    )
    await session.commit()
    return await get_target(session, tid)


async def get_target(session: AsyncSession, target_id: str) -> dict[str, Any]:
    await ensure_f7_tables(session)
    row = (
        await session.execute(
            text(
                """
                select target_id, account_id, name, website_url, source, last_scanned_at, created_at
                from signal_scout_targets where target_id = :tid
                """
            ),
            {"tid": target_id},
        )
    ).mappings().first()
    if not row:
        raise NotFoundError("target")

    crm_extra: dict[str, Any] = {}
    if row.get("account_id"):
        crm = (
            await session.execute(
                text(
                    """
                    select deal_status, recovery_eligibility, signal_detected, signal_title,
                           signal_classification, signal_source_url, as_of_date::text as as_of_date
                    from crm_master where account_id = :aid
                    """
                ),
                {"aid": row["account_id"]},
            )
        ).mappings().first()
        if crm:
            crm_extra = {
                "deal_status": crm["deal_status"],
                "recovery_eligibility": crm["recovery_eligibility"],
                "signal_on_file": {
                    "detected": bool(crm["signal_detected"]),
                    "title": crm["signal_title"],
                    "classification": crm["signal_classification"],
                    "source_url": crm["signal_source_url"],
                },
                "as_of_date": crm["as_of_date"],
                "recovery_link": (
                    f"/recovery/{row['account_id']}"
                    if crm["deal_status"] in {"lost", "inactive"}
                    and crm.get("recovery_eligibility") in {"eligible", "review"}
                    else None
                ),
            }

    running = await session.scalar(
        text(
            """
            select scan_id from signal_scout_scans
            where target_id = :tid and status in ('queued','running')
            order by started_at desc nulls last
            limit 1
            """
        ),
        {"tid": target_id},
    )

    return {
        "target_id": row["target_id"],
        "account_id": row.get("account_id"),
        "name": row["name"],
        "website_url": row["website_url"],
        "source": row["source"],
        "last_scanned_at": row["last_scanned_at"].isoformat() if row.get("last_scanned_at") else None,
        "scan_in_progress": bool(running),
        "active_scan_id": running,
        **crm_extra,
        "notice": (
            "Public sources only. Potential opportunities are not committed pipeline."
        ),
        "data_label": "Fictional demo data" if row.get("account_id") else "Manual scout target",
    }


async def list_signals(session: AsyncSession, target_id: str) -> dict[str, Any]:
    await ensure_f7_tables(session)
    await get_target(session, target_id)
    rows = (
        await session.execute(
            text(
                """
                select signal_id, target_id, scan_id, signal_type, title, summary, status, evidence, created_at
                from signal_scout_signals
                where target_id = :tid
                order by created_at desc
                """
            ),
            {"tid": target_id},
        )
    ).mappings().all()
    items = []
    for r in rows:
        items.append(
            {
                **dict(r),
                "evidence": r["evidence"] if isinstance(r["evidence"], list) else json.loads(r["evidence"] or "[]"),
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            }
        )
    return {"target_id": target_id, "items": items, "total": len(items)}


async def list_opportunities(session: AsyncSession, target_id: str) -> dict[str, Any]:
    await ensure_f7_tables(session)
    await get_target(session, target_id)
    rows = (
        await session.execute(
            text(
                """
                select opportunity_id, target_id, scan_id, title, summary, score, factors,
                       signal_ids, signal_types, status, explanation, created_at
                from signal_scout_opportunities
                where target_id = :tid
                order by score desc, created_at desc
                """
            ),
            {"tid": target_id},
        )
    ).mappings().all()
    items = []
    for r in rows:
        d = dict(r)
        for key in ("factors", "signal_ids", "signal_types", "explanation"):
            if isinstance(d.get(key), str):
                d[key] = json.loads(d[key])
        d["created_at"] = r["created_at"].isoformat() if r.get("created_at") else None
        items.append(d)
    return {
        "target_id": target_id,
        "items": items,
        "total": len(items),
        "notice": "Potential ≠ committed pipeline. Score is rules-only.",
    }


async def get_opportunity(session: AsyncSession, opportunity_id: str) -> dict[str, Any]:
    await ensure_f7_tables(session)
    row = (
        await session.execute(
            text(
                """
                select opportunity_id, target_id, scan_id, title, summary, score, factors,
                       signal_ids, signal_types, status, explanation, created_at
                from signal_scout_opportunities where opportunity_id = :oid
                """
            ),
            {"oid": opportunity_id},
        )
    ).mappings().first()
    if not row:
        raise NotFoundError("opportunity")
    d = dict(row)
    for key in ("factors", "signal_ids", "signal_types", "explanation"):
        if isinstance(d.get(key), str):
            d[key] = json.loads(d[key])
    d["created_at"] = row["created_at"].isoformat() if row.get("created_at") else None

    sig_ids = set(d.get("signal_ids") or [])
    signals = []
    rows = (
        await session.execute(
            text(
                """
                select signal_id, signal_type, title, summary, evidence
                from signal_scout_signals
                where target_id = :tid
                """
            ),
            {"tid": d["target_id"]},
        )
    ).mappings().all()
    for s in rows:
        if s["signal_id"] not in sig_ids:
            continue
        evidence = s["evidence"]
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        signals.append({**dict(s), "evidence": evidence})
    d["signals"] = signals
    d["notice"] = "Potential opportunity only — not an RFP forecast."
    return d
