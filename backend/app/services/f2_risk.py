from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.scoring.risk_score import RISK_BAND_SOURCE, SCORING_VERSION, compute_risk_score
from app.services.f2_llm import llm_explain_risk


class ConfirmationRequiredError(AppError):
    status_code = 422
    code = "CONFIRMATION_REQUIRED"
    message = "Confirmation is required before writing to CRM."


class ValidationAppError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "The request is not valid."


RISK_SELECT = """
select account_id, account_name, opportunity_id, opportunity_name, deal_status,
       opportunity_stage, deal_value, currency, contact_name, contact_email,
       contact_designation, is_decision_maker, account_owner,
       revenue_risk_score, risk_category, risk_reason, recommended_next_action,
       inactivity_days, last_activity_date::text as last_activity_date,
       expected_close_date::text as expected_close_date,
       next_followup_date::text as next_followup_date,
       next_action, next_action_date::text as next_action_date,
       blocker_detected, blocker_category, blocker_severity, blocker_status,
       competitor_category, competitor_notes,
       signal_type, signal_title, signal_description,
       signal_published_date::text as signal_published_date,
       previous_interaction_summary, customer_objections, customer_requirements,
       sales_engagement_count, product_interest, product_reference,
       as_of_date::text as as_of_date, activity_history, record_segment
from crm_master
"""


def _row(mapping: Any) -> dict[str, Any]:
    return dict(mapping)


def _parse_history(raw: Any) -> list:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)
    return []


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _is_overdue(row: dict[str, Any]) -> bool:
    as_of = _parse_date(row.get("as_of_date")) or date(2026, 11, 4)
    for key in ("next_followup_date", "next_action_date"):
        d = _parse_date(row.get(key))
        if d is not None and d < as_of:
            return True
    return False


def _display_band(row: dict[str, Any], computed: dict[str, Any] | None = None) -> str:
    """MVP: prefer stored risk_category for list; fall back to computed."""
    stored = (row.get("risk_category") or "").lower()
    if stored in {"high", "medium", "low"}:
        return stored
    if computed:
        return computed["risk_category"]
    return "low"


def _display_score(row: dict[str, Any], computed: dict[str, Any] | None = None) -> int:
    if row.get("revenue_risk_score") is not None:
        try:
            return int(row["revenue_risk_score"])
        except (TypeError, ValueError):
            pass
    if computed:
        return int(computed["revenue_risk_score"])
    return 0


async def list_risk(
    session: AsyncSession,
    *,
    band: str | None = None,
    deal_status: str | None = None,
    preset: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    where = ["deal_status in ('open', 'stalled')"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if deal_status in {"open", "stalled"}:
        where = ["deal_status = :deal_status"]
        params["deal_status"] = deal_status

    if preset == "needs_attention_today":
        where.append(
            """(
              lower(coalesce(risk_category, '')) = 'high'
              or (next_followup_date is not null and next_followup_date < as_of_date)
              or (next_action_date is not null and next_action_date < as_of_date)
            )"""
        )
    elif band in {"high", "medium", "low"}:
        where.append("lower(coalesce(risk_category, '')) = :band")
        params["band"] = band

    where_sql = " and ".join(where)

    total = await session.scalar(
        text(f"select count(*) from crm_master where {where_sql}"),
        params,
    )

    at_risk = await session.scalar(
        text(
            """
            select coalesce(sum(deal_value), 0)
            from crm_master
            where deal_status in ('open', 'stalled')
              and lower(coalesce(risk_category, '')) = 'high'
            """
        )
    )

    rows = (
        await session.execute(
            text(
                f"""
                {RISK_SELECT}
                where {where_sql}
                order by revenue_risk_score desc nulls last,
                         deal_value desc nulls last,
                         account_id
                limit :limit offset :offset
                """
            ),
            params,
        )
    ).mappings().all()

    items = []
    for r in rows:
        d = _row(r)
        overdue = _is_overdue(d)
        items.append(
            {
                "account_id": d["account_id"],
                "account_name": d["account_name"],
                "opportunity_name": d["opportunity_name"],
                "opportunity_stage": d["opportunity_stage"],
                "deal_status": d["deal_status"],
                "deal_value": float(d["deal_value"] or 0),
                "currency": d["currency"] or "USD",
                "revenue_risk_score": _display_score(d),
                "risk_category": _display_band(d),
                "top_reason": (d.get("risk_reason") or "")[:120] or None,
                "inactivity_days": d["inactivity_days"],
                "expected_close_date": d["expected_close_date"],
                "blocker_category": d["blocker_category"] if d.get("blocker_detected") else None,
                "blocker_severity": d["blocker_severity"] if d.get("blocker_detected") else None,
                "overdue_followup": overdue,
                "next_followup_date": d["next_followup_date"],
                "recommended_next_action": d["recommended_next_action"],
                "data_label": "Fictional demo data",
            }
        )

    return {
        "items": items,
        "total": int(total or 0),
        "limit": limit,
        "offset": offset,
        "at_risk_usd": float(at_risk or 0),
        "at_risk_note": "At-risk value is not lost revenue.",
        "preset": preset,
        "band": band,
        "risk_band_source": RISK_BAND_SOURCE,
        "scoring_version": SCORING_VERSION,
        "data_label": "Fictional demo data",
    }


async def get_risk_row(session: AsyncSession, account_id: str) -> dict[str, Any]:
    result = await session.execute(
        text(f"{RISK_SELECT} where account_id = :account_id"),
        {"account_id": account_id},
    )
    row = result.mappings().first()
    if not row:
        raise NotFoundError(f"Account {account_id} not found")
    d = _row(row)
    if d["deal_status"] not in {"open", "stalled"}:
        raise ValidationAppError("Risk view is for open or stalled deals only.")
    return d


def _build_evidence(row: dict[str, Any], computed: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    evidence.append(
        {
            "id": "E1",
            "source_type": "crm_deal",
            "source_id": row["account_id"],
            "title": row.get("opportunity_name") or row["account_name"],
            "date": row.get("as_of_date") or "unavailable",
            "snippet": (
                f"Stored risk score {row.get('revenue_risk_score')} "
                f"({row.get('risk_category')}); rules recompute {computed['revenue_risk_score']} "
                f"({computed['risk_category']})."
            ),
            "relationship": "supports",
        }
    )
    if row.get("last_activity_date"):
        evidence.append(
            {
                "id": "E2",
                "source_type": "activity",
                "source_id": row["account_id"],
                "title": "Last activity",
                "date": row["last_activity_date"],
                "snippet": f"{computed['days_inactive']} days inactive as of {row.get('as_of_date')}.",
                "relationship": "supports",
            }
        )
    if row.get("blocker_detected"):
        evidence.append(
            {
                "id": "E3",
                "source_type": "crm_deal",
                "source_id": row["account_id"],
                "title": f"Blocker: {row.get('blocker_category') or 'open'}",
                "date": row.get("as_of_date") or "unavailable",
                "snippet": (
                    f"Severity {row.get('blocker_severity')}, status {row.get('blocker_status')}."
                ),
                "relationship": "supports",
            }
        )
    if row.get("previous_interaction_summary"):
        evidence.append(
            {
                "id": "E4",
                "source_type": "activity",
                "source_id": row["account_id"],
                "title": "Previous interaction",
                "date": row.get("last_activity_date") or "unavailable",
                "snippet": str(row["previous_interaction_summary"])[:280],
                "relationship": "context",
            }
        )
    return evidence


def _rule_explanation(row: dict[str, Any], computed: dict[str, Any]) -> dict[str, Any]:
    facts = [
        {
            "layer": "fact",
            "text": (
                f"{row['account_name']} is {row['deal_status']} with stored risk score "
                f"{row.get('revenue_risk_score')} ({row.get('risk_category')})."
            ),
        },
        {
            "layer": "fact",
            "text": (
                f"Rules ({SCORING_VERSION}) compute {computed['revenue_risk_score']}/100 "
                f"({computed['risk_category']}): {computed['risk_reason']}"
            ),
        },
    ]
    if row.get("blocker_detected"):
        facts.append(
            {
                "layer": "fact",
                "text": (
                    f"Blocker on record: {row.get('blocker_category')} "
                    f"({row.get('blocker_severity')}, {row.get('blocker_status')})."
                ),
            }
        )
    interpretation = {
        "text": row.get("risk_reason")
        or "Open opportunity shows elevated attention factors from stored CRM fields."
    }
    action = {
        "text": row.get("recommended_next_action")
        or "Review the factor evidence and consider logging the next follow-up."
    }
    return {
        "facts": facts,
        "interpretation": interpretation,
        "recommended_action": action,
        "source": "rules",
    }


async def get_risk_detail(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = await get_risk_row(session, account_id)
    computed = compute_risk_score(row)
    explanation = _rule_explanation(row, computed)
    history = _parse_history(row.get("activity_history"))
    timeline = sorted(
        [h for h in history if isinstance(h, dict)],
        key=lambda a: str(a.get("date") or ""),
        reverse=True,
    )[:5]

    return {
        "account_id": row["account_id"],
        "account_name": row["account_name"],
        "opportunity_id": row["opportunity_id"],
        "opportunity_name": row["opportunity_name"],
        "deal_status": row["deal_status"],
        "opportunity_stage": row["opportunity_stage"],
        "deal_value": float(row["deal_value"] or 0),
        "currency": row["currency"] or "USD",
        "contact_name": row["contact_name"],
        "contact_email": row["contact_email"],
        "is_decision_maker": bool(row.get("is_decision_maker")),
        "account_owner": row["account_owner"],
        "revenue_risk_score": _display_score(row, computed),
        "risk_category": _display_band(row, computed),
        "risk_reason": row.get("risk_reason") or computed["risk_reason"],
        "recommended_next_action": row["recommended_next_action"],
        "inactivity_days": computed["days_inactive"],
        "last_activity_date": row["last_activity_date"],
        "expected_close_date": row["expected_close_date"],
        "next_followup_date": row["next_followup_date"],
        "next_action": row["next_action"],
        "next_action_date": row["next_action_date"],
        "overdue_followup": computed["overdue_followup"],
        "blocker": {
            "detected": bool(row.get("blocker_detected")),
            "category": row.get("blocker_category"),
            "severity": row.get("blocker_severity"),
            "status": row.get("blocker_status"),
        },
        "competitor_category": row.get("competitor_category"),
        "factors": computed["factors"],
        "computed_score": computed["revenue_risk_score"],
        "computed_band": computed["risk_category"],
        "scoring_version": SCORING_VERSION,
        "evidence": _build_evidence(row, computed),
        "explanation": explanation,
        "timeline": timeline,
        "as_of_date": row["as_of_date"],
        "data_label": "Fictional demo data",
    }


async def recompute_and_persist(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = await get_risk_row(session, account_id)
    computed = compute_risk_score(row)
    await session.execute(
        text(
            """
            update crm_master
            set revenue_risk_score = :score,
                risk_category = :band,
                risk_reason = :reason
            where account_id = :account_id
            """
        ),
        {
            "score": computed["revenue_risk_score"],
            "band": computed["risk_category"],
            "reason": computed["risk_reason"],
            "account_id": account_id,
        },
    )
    await session.commit()
    return {
        "account_id": account_id,
        "revenue_risk_score": computed["revenue_risk_score"],
        "risk_category": computed["risk_category"],
        "risk_reason": computed["risk_reason"],
        "factors": computed["factors"],
        "scoring_version": SCORING_VERSION,
        "source": "rules",
    }


async def explain_risk(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = await get_risk_row(session, account_id)
    computed = compute_risk_score(row)
    base = _rule_explanation(row, computed)
    llm = await llm_explain_risk(row, computed)
    if llm:
        base["interpretation"] = {"text": llm["interpretation"]}
        base["recommended_action"] = {"text": llm["recommended_action"]}
        base["source"] = "azure_openai"
    else:
        base["source"] = "rules_fallback"
        base["ai_unavailable"] = True
    base["revenue_risk_score"] = _display_score(row, computed)
    base["risk_category"] = _display_band(row, computed)
    base["scoring_version"] = SCORING_VERSION
    base["account_id"] = account_id
    base["data_label"] = "Fictional demo data"
    return base


async def preview_action_log(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = await get_risk_row(session, account_id)
    as_of = row.get("as_of_date") or date(2026, 11, 4).isoformat()
    action = row.get("recommended_next_action") or "Follow up on open risk factors"
    next_date = (date.fromisoformat(str(as_of)[:10]) + timedelta(days=3)).isoformat()
    return {
        "account_id": account_id,
        "requires_confirmation": True,
        "summary": "Log recommended risk follow-up as a CRM note and set next action date.",
        "recommended_next_action": action,
        "proposed_activity": {
            "date": as_of,
            "type": "Note",
            "direction": "internal",
            "description": f"Risk follow-up committed: {action}",
            "outcome": "Action logged by salesperson",
            "classification": "SYNTHETIC",
        },
        "field_updates": {
            "next_action": action,
            "next_action_date": next_date,
            "next_followup_date": next_date,
            "last_activity_date": as_of,
            "inactivity_days": 0,
        },
        "will_not_change": [
            "deal_status (remains open/stalled)",
            "deal_value",
            "At-risk value is not lost revenue",
            "No auto-mark lost or won",
        ],
        "data_label": "Fictional demo data",
    }


async def confirm_action_log(
    session: AsyncSession, account_id: str, confirm: bool
) -> dict[str, Any]:
    if not confirm:
        raise ConfirmationRequiredError()
    preview = await preview_action_log(session, account_id)
    row = await get_risk_row(session, account_id)
    history = _parse_history(row.get("activity_history"))
    history.append(preview["proposed_activity"])
    updates = preview["field_updates"]
    await session.execute(
        text(
            """
            update crm_master
            set activity_history = cast(:history as jsonb),
                next_action = :next_action,
                next_action_date = cast(:next_action_date as date),
                next_followup_date = cast(:next_followup_date as date),
                last_activity_date = cast(:as_of as date),
                inactivity_days = 0
            where account_id = :account_id
            """
        ),
        {
            "history": json.dumps(history),
            "next_action": updates["next_action"],
            "next_action_date": updates["next_action_date"],
            "next_followup_date": updates["next_followup_date"],
            "as_of": updates["last_activity_date"],
            "account_id": account_id,
        },
    )
    await session.commit()
    recomputed = await recompute_and_persist(session, account_id)
    return {
        "ok": True,
        "account_id": account_id,
        "recomputed": recomputed,
    }
