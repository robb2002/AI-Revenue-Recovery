from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.services.f1_llm import llm_draft, llm_explanation
from app.services.f1_samples import render_sample


def _parse_history(raw: Any) -> list[dict[str, Any]]:
    history = raw
    if isinstance(history, str):
        try:
            history = json.loads(history)
        except json.JSONDecodeError:
            history = []
    if history is None:
        history = []
    if not isinstance(history, list):
        return []
    return [h for h in history if isinstance(h, dict)]


class ConfirmationRequiredError(AppError):
    status_code = 422
    code = "CONFIRMATION_REQUIRED"
    message = "Confirmation is required before writing to CRM."


class ValidationAppError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "The request is not valid."


RECOVERY_SELECT = """
select account_id, account_name, opportunity_id, opportunity_name, deal_status, deal_value,
       currency, contact_name, contact_email, contact_designation, account_owner,
       lost_reason, inactivity_days, last_activity_date::text as last_activity_date,
       last_contacted_date::text as last_contacted_date,
       signal_detected, signal_title, signal_description, signal_source_url,
       signal_classification, signal_published_date::text as signal_published_date,
       recovery_eligibility, recommended_next_action, next_followup_recommendation,
       followup_email_subject, followup_email_body, followup_message_status,
       customer_requirements_summary, previous_interaction_summary,
       as_of_date::text as as_of_date, activity_history
from crm_master
"""


def _row(mapping: Any) -> dict[str, Any]:
    return dict(mapping)


async def list_recovery(
    session: AsyncSession,
    *,
    eligibility: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    where = ["deal_status in ('lost', 'inactive')"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if eligibility in {"eligible", "review"}:
        where.append("recovery_eligibility = :eligibility")
        params["eligibility"] = eligibility
    else:
        where.append("coalesce(recovery_eligibility, '') in ('eligible', 'review')")

    where_sql = " and ".join(where)
    total = await session.scalar(
        text(f"select count(*) from crm_master where {where_sql}"),
        params,
    )
    rows = (
        await session.execute(
            text(
                f"""
                {RECOVERY_SELECT}
                where {where_sql}
                order by
                  case when signal_classification = 'PUBLIC_VERIFIED' then 0 else 1 end,
                  case when recovery_eligibility = 'eligible' then 0 else 1 end,
                  deal_value desc nulls last,
                  inactivity_days desc nulls last
                limit :limit offset :offset
                """
            ),
            params,
        )
    ).mappings().all()

    items = []
    for r in rows:
        d = _row(r)
        items.append(
            {
                "account_id": d["account_id"],
                "account_name": d["account_name"],
                "opportunity_name": d["opportunity_name"],
                "deal_status": d["deal_status"],
                "deal_value": float(d["deal_value"] or 0),
                "currency": d["currency"] or "USD",
                "lost_reason": d["lost_reason"],
                "inactivity_days": d["inactivity_days"],
                "recovery_eligibility": d["recovery_eligibility"],
                "signal_title": d["signal_title"],
                "signal_classification": d["signal_classification"],
                "signal_source_url": d["signal_source_url"]
                if d["signal_classification"] == "PUBLIC_VERIFIED"
                else None,
                "followup_message_status": d["followup_message_status"],
                "draft_subject_preview": (d["followup_email_subject"] or "")[:80] or None,
                "data_label": "Fictional demo data",
            }
        )
    return {
        "items": items,
        "total": int(total or 0),
        "limit": limit,
        "offset": offset,
        "data_label": "Fictional demo data",
    }


async def get_recovery_row(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = (
        await session.execute(
            text(f"{RECOVERY_SELECT} where account_id = :account_id"),
            {"account_id": account_id},
        )
    ).mappings().first()
    if not row:
        raise NotFoundError("account")
    return _row(row)


def _facts_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    lost = row.get("lost_reason") or "No lost reason stored."
    inactivity = row.get("inactivity_days")
    last = row.get("last_activity_date") or "unavailable"
    signal_title = row.get("signal_title")
    signal_class = row.get("signal_classification")
    facts = [
        {
            "layer": "fact",
            "text": f"Lost/inactive reason on file: {lost}",
            "evidence": [{"source_type": "crm_deal", "snippet": str(lost)[:240]}],
        },
        {
            "layer": "fact",
            "text": f"Inactivity: {inactivity} days as of {row.get('as_of_date')}; last activity {last}.",
            "evidence": [{"source_type": "activity", "snippet": f"last_activity_date={last}"}],
        },
    ]
    if signal_title:
        facts.append(
            {
                "layer": "fact",
                "text": f"Stored signal: {signal_title} ({signal_class or 'unclassified'}).",
                "evidence": [
                    {
                        "source_type": "company_signal",
                        "snippet": (row.get("signal_description") or signal_title)[:240],
                        "url": row.get("signal_source_url")
                        if signal_class == "PUBLIC_VERIFIED"
                        else None,
                    }
                ],
            }
        )
    return facts


def build_explanation_fallback(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "facts": _facts_from_row(row),
        "interpretation": {
            "layer": "interpretation",
            "text": (
                "This account may be worth reviewing because stored inactivity and/or a public "
                "signal suggest timing could have changed — not a guarantee of recovery."
            ),
        },
        "recommended_action": {
            "layer": "recommended_action",
            "text": row.get("recommended_next_action")
            or row.get("next_followup_recommendation")
            or "Draft a short re-engagement check-in and log it to CRM only after approval.",
        },
        "ai_source": "rules",
    }


async def build_explanation(row: dict[str, Any]) -> dict[str, Any]:
    base = build_explanation_fallback(row)
    llm = await llm_explanation(row)
    if not llm:
        return base
    base["interpretation"] = {"layer": "interpretation", "text": llm["interpretation"]}
    base["recommended_action"] = {
        "layer": "recommended_action",
        "text": llm["recommended_action"],
    }
    base["ai_source"] = "azure_openai"
    return base


async def get_recovery_detail(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = await get_recovery_row(session, account_id)
    explanation = await build_explanation(row)
    return {
        "account_id": row["account_id"],
        "account_name": row["account_name"],
        "opportunity_id": row["opportunity_id"],
        "opportunity_name": row["opportunity_name"],
        "deal_status": row["deal_status"],
        "deal_value": float(row["deal_value"] or 0),
        "currency": row["currency"] or "USD",
        "contact_name": row["contact_name"],
        "contact_email": row["contact_email"],
        "contact_designation": row["contact_designation"],
        "account_owner": row["account_owner"],
        "lost_reason": row["lost_reason"],
        "inactivity_days": row["inactivity_days"],
        "last_activity_date": row["last_activity_date"],
        "recovery_eligibility": row["recovery_eligibility"],
        "signal": {
            "title": row["signal_title"],
            "description": row["signal_description"],
            "classification": row["signal_classification"],
            "published_date": row["signal_published_date"],
            "source_url": row["signal_source_url"]
            if row["signal_classification"] == "PUBLIC_VERIFIED"
            else None,
        },
        "explanation": explanation,
        "draft": {
            "draft_type": "reengagement_email",
            "subject": row["followup_email_subject"],
            "body": row["followup_email_body"],
            "state": row["followup_message_status"] or "draft",
        },
        "as_of_date": row["as_of_date"],
        "data_label": "Fictional demo data",
    }


async def generate_reengagement(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = await get_recovery_row(session, account_id)
    source = "sample"
    draft = await llm_draft(row)
    if draft:
        source = "azure_openai"
    else:
        draft = render_sample(
            account_id,
            row.get("contact_name") or "",
            row.get("account_owner") or "",
            row.get("lost_reason") or "",
        )
        if draft is None:
            source = "template"
            draft = {
                "subject": f"Reconnecting — {row.get('account_name') or account_id}",
                "body": (
                    f"Hi {row.get('contact_name') or 'there'},\n\n"
                    f"I wanted to reconnect regarding {row.get('opportunity_name') or 'our prior discussion'}. "
                    f"Previous note on file: {row.get('lost_reason') or 'timing'}.\n\n"
                    "Would a short check-in next week work?\n\n"
                    f"Best regards,\n{row.get('account_owner') or 'Lumora Sales'}\nLumora Learning"
                ),
            }
        else:
            source = "sample"
    await session.execute(
        text(
            """
            update crm_master
            set followup_email_subject = :subject,
                followup_email_body = :body,
                followup_message_status = 'draft'
            where account_id = :account_id
            """
        ),
        {"subject": draft["subject"], "body": draft["body"], "account_id": account_id},
    )
    await session.commit()
    return {
        "draft_type": "reengagement_email",
        "subject": draft["subject"],
        "body": draft["body"],
        "state": "draft",
        "source": source,
    }


async def patch_reengagement(
    session: AsyncSession, account_id: str, subject: str | None, body: str | None
) -> dict[str, Any]:
    row = await get_recovery_row(session, account_id)
    status = row.get("followup_message_status") or "draft"
    if status not in {"draft", None}:
        raise ValidationAppError("Draft is not editable in the current state.")
    new_subject = subject if subject is not None else row.get("followup_email_subject")
    new_body = body if body is not None else row.get("followup_email_body")
    await session.execute(
        text(
            """
            update crm_master
            set followup_email_subject = :subject,
                followup_email_body = :body,
                followup_message_status = 'draft'
            where account_id = :account_id
            """
        ),
        {"subject": new_subject, "body": new_body, "account_id": account_id},
    )
    await session.commit()
    return {
        "draft_type": "reengagement_email",
        "subject": new_subject,
        "body": new_body,
        "state": "draft",
    }


async def set_draft_state(session: AsyncSession, account_id: str, state: str) -> dict[str, str]:
    await get_recovery_row(session, account_id)
    if state not in {"approved", "rejected", "draft"}:
        raise ValidationAppError("Invalid draft state.")
    await session.execute(
        text(
            "update crm_master set followup_message_status = :state where account_id = :account_id"
        ),
        {"state": state, "account_id": account_id},
    )
    await session.commit()
    return {"state": state}


async def preview_crm_log(
    session: AsyncSession,
    account_id: str,
    *,
    source: str = "draft",
    gmail_message_id: str | None = None,
) -> dict[str, Any]:
    del gmail_message_id  # inbox approve uses /gmail/inbox/* — recovery keeps draft-only CRM log
    row = await get_recovery_row(session, account_id)
    as_of = row.get("as_of_date") or date.today().isoformat()
    source_norm = (source or "draft").strip().lower()
    if source_norm != "draft":
        raise ValidationAppError(
            "Use Briefing → Inbox leads to approve Gmail into CRM. Recovery CRM log is draft-only."
        )

    subject = row.get("followup_email_subject")
    body = row.get("followup_email_body")
    if not subject or not body:
        raise ValidationAppError("Generate or save a draft before logging to CRM.")
    return {
        "account_id": account_id,
        "source": "draft",
        "requires_confirmation": True,
        "summary": "Log outbound re-engagement draft and refresh last-contact fields.",
        "proposed_activity": {
            "date": as_of,
            "type": "Email",
            "direction": "outbound",
            "description": f"Re-engagement check-in: {subject}",
            "outcome": "Awaiting customer reply",
            "classification": "SYNTHETIC",
        },
        "field_updates": {
            "last_contacted_date": as_of,
            "last_activity_date": as_of,
            "inactivity_days": 0,
            "followup_message_status": "approved",
            "followup_email_subject": subject,
        },
        "will_not_change": [
            "deal_status (remains lost/inactive until Reopen)",
            "deal_value",
            "signal_source_url",
            "recovery is not marked as revenue recovered",
            "email is not sent",
        ],
        "data_label": "Fictional demo data",
    }


async def confirm_crm_log(
    session: AsyncSession,
    account_id: str,
    confirm: bool,
    *,
    source: str = "draft",
    gmail_message_id: str | None = None,
) -> dict[str, Any]:
    if not confirm:
        raise ConfirmationRequiredError()
    preview = await preview_crm_log(
        session, account_id, source=source, gmail_message_id=gmail_message_id
    )
    row = await get_recovery_row(session, account_id)
    history = _parse_history(row.get("activity_history"))
    history.append(preview["proposed_activity"])
    as_of = preview["field_updates"]["last_contacted_date"]
    await session.execute(
        text(
            """
            update crm_master
            set activity_history = cast(:history as jsonb),
                last_contacted_date = cast(:as_of as date),
                last_activity_date = cast(:as_of as date),
                inactivity_days = 0,
                followup_message_status = 'approved'
            where account_id = :account_id
            """
        ),
        {
            "history": json.dumps(history),
            "as_of": as_of,
            "account_id": account_id,
        },
    )
    await session.commit()
    return {
        "ok": True,
        "account_id": account_id,
        "source": "draft",
        "followup_message_status": "approved",
    }

async def reopen(session: AsyncSession, account_id: str, confirm: bool) -> dict[str, Any]:
    if not confirm:
        raise ConfirmationRequiredError()
    row = await get_recovery_row(session, account_id)
    if row["deal_status"] not in {"lost", "inactive"}:
        raise ValidationAppError("Only lost or inactive deals can be reopened.")
    note = {
        "date": row.get("as_of_date") or datetime.now(timezone.utc).date().isoformat(),
        "type": "Note",
        "direction": "internal",
        "description": "Opportunity reopened by salesperson (not marked recovered revenue).",
        "outcome": "Status set to open",
        "classification": "SYNTHETIC",
    }
    history = _parse_history(row.get("activity_history"))
    history.append(note)
    await session.execute(
        text(
            """
            update crm_master
            set deal_status = 'open',
                recovery_eligibility = null,
                activity_history = cast(:history as jsonb)
            where account_id = :account_id
            """
        ),
        {"history": json.dumps(history), "account_id": account_id},
    )
    await session.commit()
    return {"ok": True, "account_id": account_id, "deal_status": "open"}
