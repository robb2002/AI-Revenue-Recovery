"""F6 — Mark won + customer handoff pack (crm_master handoff_* columns)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    text_ = str(value or "2026-11-04")[:10]
    return date.fromisoformat(text_)

SELECT = """
select account_id, account_name, opportunity_id, opportunity_name, deal_status, deal_value,
       currency, contact_name, contact_designation, account_owner, is_decision_maker,
       product_interest, recommended_products, product_reference,
       customer_requirements, customer_requirements_summary, pain_points, customer_objections,
       blocker_detected, blocker_category, blocker_description, blocker_status,
       purchase_timeline, implementation_timeline,
       implementation_requirements, implementation_risks, delivery_commitments,
       onboarding_checklist, stakeholders, handoff_stakeholders, sales_handoff_summary,
       handoff_required, handoff_status, handoff_created_date::text as handoff_created_date,
       proposal_status, proposal_title, proposal_draft, meeting_summary, activity_history,
       as_of_date::text as as_of_date
from crm_master
where account_id = :aid
"""


class ConfirmRequiredError(AppError):
    status_code = 400
    code = "CONFIRM_REQUIRED"
    message = "Confirmation is required before marking the deal won."


class AlreadyWonError(AppError):
    status_code = 409
    code = "ALREADY_WON"
    message = "This deal is already won."


class DealNotWonError(AppError):
    status_code = 409
    code = "DEAL_NOT_WON"
    message = "Handoff is only available after the deal is marked won."


class HandoffNotDraftError(AppError):
    status_code = 409
    code = "HANDOFF_NOT_DRAFT"
    message = "Handoff is not in a draft state."


class ValidationAppError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "The request is not valid."


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _normalize_status(raw: str | None) -> str:
    s = (raw or "none").lower()
    if s in {"approved", "completed"}:
        return "approved"
    if s in {"draft", "pending", "in_progress"}:
        return "draft"
    if s in {"rejected"}:
        return "rejected"
    return s or "none"


async def _load(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = (await session.execute(text(SELECT), {"aid": account_id})).mappings().first()
    if not row:
        raise NotFoundError("account")
    return dict(row)


def _stakeholders(row: dict[str, Any]) -> list[dict[str, Any]]:
    source = _list(row.get("handoff_stakeholders")) or _list(row.get("stakeholders"))
    out: list[dict[str, Any]] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "name": item.get("name") or "Unknown",
                "role": item.get("title") or item.get("role") or "stakeholder",
                "is_decision_maker": (item.get("role") or "").lower()
                in {"decision_maker", "decision-maker", "champion"},
            }
        )
    if not out and row.get("contact_name"):
        out.append(
            {
                "name": row["contact_name"],
                "role": row.get("contact_designation") or "contact",
                "is_decision_maker": bool(row.get("is_decision_maker")),
            }
        )
    return out


def _confirmed_requirements(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in _list(row.get("customer_requirements")):
        if not isinstance(item, dict):
            continue
        st = (item.get("status") or "").lower()
        # Prefer confirmed; for won rows many are unconfirmed in seed — include must_have too
        if st in {"confirmed", "unconfirmed", ""} or item.get("priority") == "must_have":
            text_ = (item.get("requirement") or "").strip()
            if text_ and text_ not in out:
                out.append(text_)
    for item in _list(row.get("implementation_requirements")):
        if isinstance(item, dict) and item.get("requirement"):
            t = str(item["requirement"]).strip()
            if t and t not in out:
                out.append(t)
    return out[:12]


def _open_items(row: dict[str, Any]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()

    def add(text_: str) -> None:
        t = text_.strip()
        if t and t not in seen:
            seen.add(t)
            items.append(t)

    if row.get("blocker_detected") and (row.get("blocker_status") or "").lower() in {
        "open",
        "in_progress",
    }:
        add(
            f"Open blocker: {row.get('blocker_category') or 'blocker'} "
            f"({row.get('blocker_status')})"
        )
    for item in _list(row.get("implementation_risks")):
        if isinstance(item, dict) and item.get("risk"):
            add(str(item["risk"]))
    for item in _list(row.get("customer_objections")):
        if isinstance(item, dict) and (item.get("status") or "open").lower() == "open":
            if item.get("objection"):
                add(str(item["objection"]))
    return items[:10]


def _products(row: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in _list(row.get("product_reference")):
        if not isinstance(item, dict):
            continue
        name = str(item.get("product_name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "reference_url": str(item.get("source_url") or ""),
                "claim_text": str(item.get("claim_text") or "")[:240],
            }
        )
    if not out and row.get("product_interest"):
        out.append({"name": str(row["product_interest"]), "reference_url": "", "claim_text": ""})
    return out[:6]


def _proposal_summary(row: dict[str, Any]) -> str | None:
    if (row.get("proposal_status") or "").lower() != "approved":
        return None
    draft = row.get("proposal_draft")
    if isinstance(draft, str):
        try:
            draft = json.loads(draft)
        except json.JSONDecodeError:
            draft = None
    if isinstance(draft, dict):
        return str(
            draft.get("executive_summary")
            or draft.get("proposed_solution")
            or draft.get("title")
            or row.get("proposal_title")
            or ""
        )[:800] or None
    return row.get("proposal_title")


def _checklist(row: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for item in _list(row.get("onboarding_checklist")):
        if isinstance(item, dict) and item.get("task"):
            out.append(
                {
                    "task": item.get("task"),
                    "owner": item.get("owner") or "Delivery",
                    "status": item.get("status") or "todo",
                    "due_date": item.get("due_date"),
                }
            )
    return out


def _assemble_pack(row: dict[str, Any]) -> dict[str, Any]:
    timeline = []
    if row.get("implementation_timeline"):
        timeline.append(str(row["implementation_timeline"]))
    if row.get("purchase_timeline"):
        timeline.append(f"Purchase timing on file: {row['purchase_timeline']}")
    for item in _list(row.get("delivery_commitments")):
        if isinstance(item, dict) and item.get("commitment"):
            due = item.get("due_date") or "TBD"
            timeline.append(f"{due}: {item['commitment']}")

    return {
        "classification": "AI_GENERATED",
        "simulated": True,
        "requires_human_approval": True,
        "account_id": row["account_id"],
        "opportunity_name": row.get("opportunity_name"),
        "stakeholders": _stakeholders(row),
        "confirmed_requirements": _confirmed_requirements(row),
        "open_items": _open_items(row),
        "timeline": timeline[:8],
        "products": _products(row),
        "proposal_summary": _proposal_summary(row),
        "delivery_notes": row.get("sales_handoff_summary")
        or row.get("meeting_summary")
        or "No handoff summary on file yet.",
        "checklist": _checklist(row),
        "evidence": [
            {"source_type": "crm_deal", "snippet": f"deal_status={row.get('deal_status')}"},
            *(
                [{"source_type": "meeting", "snippet": str(row["meeting_summary"])[:180]}]
                if row.get("meeting_summary")
                else []
            ),
        ],
    }


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    status = _normalize_status(row.get("handoff_status"))
    has_content = bool(
        row.get("sales_handoff_summary")
        or _list(row.get("handoff_stakeholders"))
        or _list(row.get("onboarding_checklist"))
    )
    pack = _assemble_pack(row) if (row.get("deal_status") == "won" and has_content) else None
    return {
        "account_id": row["account_id"],
        "account_name": row["account_name"],
        "opportunity_name": row.get("opportunity_name"),
        "deal_status": row.get("deal_status"),
        "deal_value": row.get("deal_value"),
        "currency": row.get("currency") or "USD",
        "handoff_required": bool(row.get("handoff_required")),
        "handoff_status": status,
        "handoff_created_date": row.get("handoff_created_date"),
        "handoff_pack": pack,
        "can_mark_won": row.get("deal_status") == "open",
        "notice": (
            "Handoff packs stay drafts until approved. Mark won is an explicit human action — "
            "proposal approve alone does not win the deal. Nothing is emailed to delivery."
        ),
        "data_label": "Fictional demo data",
        "as_of_date": row.get("as_of_date"),
    }


async def get_handoff(session: AsyncSession, account_id: str) -> dict[str, Any]:
    return _payload(await _load(session, account_id))


async def mark_won(session: AsyncSession, account_id: str, confirm: bool) -> dict[str, Any]:
    if not confirm:
        raise ConfirmRequiredError()
    row = await _load(session, account_id)
    if row.get("deal_status") == "won":
        raise AlreadyWonError()
    if row.get("deal_status") != "open":
        raise ValidationAppError(
            f"Only open deals can be marked won (current: {row.get('deal_status')})."
        )

    as_of = _as_date(row.get("as_of_date"))
    history = _list(row.get("activity_history"))
    history = list(history)
    history.append(
        {
            "date": as_of.isoformat(),
            "type": "note",
            "direction": "internal",
            "description": "Deal marked won by salesperson (explicit confirm). Handoff required.",
            "outcome": "won",
            "classification": "SYNTHETIC",
        }
    )

    await session.execute(
        text(
            """
            update crm_master
            set deal_status = 'won',
                opportunity_stage = 'closed',
                handoff_required = true,
                handoff_status = 'pending',
                handoff_created_date = :as_of,
                activity_history = cast(:history as jsonb)
            where account_id = :aid
            """
        ),
        {"as_of": as_of, "history": json.dumps(history), "aid": account_id},
    )
    await session.commit()
    payload = await get_handoff(session, account_id)
    payload["notice"] = (
        "Deal marked won. Generate a handoff pack for delivery. Nothing was emailed."
    )
    return payload


def _build_generated_fields(row: dict[str, Any]) -> dict[str, Any]:
    reqs = _confirmed_requirements(row)
    stakeholders = _stakeholders(row)
    # Expand to handoff_stakeholders shape
    hs = []
    for s in stakeholders:
        hs.append(
            {
                "name": s["name"],
                "role": "decision_maker" if s.get("is_decision_maker") else "stakeholder",
                "team": "Customer",
                "title": s.get("role") or "stakeholder",
            }
        )
    if row.get("account_owner"):
        hs.append(
            {
                "name": row["account_owner"],
                "role": "account_executive",
                "team": "Lumora",
                "title": "Account Executive",
            }
        )

    impl_reqs = [
        {"owner": "Implementation Lead", "priority": "must_have", "requirement": r}
        for r in reqs[:6]
    ]
    risks = []
    for item in _open_items(row):
        risks.append(
            {
                "risk": item,
                "likelihood": "medium",
                "mitigation": "Confirm at kickoff; do not invent an SLA.",
            }
        )
    if not risks:
        risks.append(
            {
                "risk": "Customer systems list not yet confirmed",
                "likelihood": "medium",
                "mitigation": "Collect the systems list at kickoff",
            }
        )

    as_of = _as_date(row.get("as_of_date")).isoformat()
    timeline = (
        f"Illustrative timeline: kickoff within 2 weeks of {as_of}, plan review 2 weeks later, "
        "first milestone review at about 90 days (SYNTHETIC). No go-live date is committed here."
    )
    commitments = [
        {
            "due_date": as_of,
            "commitment": "Hold a kickoff meeting with the customer sponsor",
            "classification": "SYNTHETIC",
        },
        {
            "due_date": as_of,
            "commitment": "Share an implementation plan for customer review",
            "classification": "SYNTHETIC",
        },
    ]
    checklist = [
        {
            "task": "Confirm kickoff date and attendees",
            "owner": "Account Executive",
            "status": "todo",
            "due_date": as_of,
        },
        {
            "task": "Collect customer systems and contact list",
            "owner": "Implementation Lead",
            "status": "todo",
            "due_date": as_of,
        },
        {
            "task": "Agree success measures with the sponsor",
            "owner": "Customer Success",
            "status": "todo",
            "due_date": as_of,
        },
    ]

    champion = row.get("contact_name") or "champion"
    title = row.get("contact_designation") or "contact"
    needs = "; ".join(reqs[:3]) if reqs else "confirm requirements at kickoff"
    summary = (
        f"Simulated won deal with {row.get('account_name')}. Champion: {champion} ({title}). "
        f"Needs: {needs}. Delivery team should confirm systems list and success measures at "
        "kickoff. Do not invent SLAs or go-live dates beyond CRM evidence."
    )
    prop = _proposal_summary(row)
    if prop:
        summary += f" Approved proposal summary on file: {prop[:240]}"

    return {
        "summary": summary,
        "handoff_stakeholders": hs,
        "implementation_requirements": impl_reqs,
        "implementation_risks": risks,
        "implementation_timeline": timeline,
        "delivery_commitments": commitments,
        "onboarding_checklist": checklist,
    }


async def generate_handoff(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = await _load(session, account_id)
    if row.get("deal_status") != "won":
        raise DealNotWonError()

    fields = _build_generated_fields(row)
    as_of = _as_date(row.get("as_of_date"))
    await session.execute(
        text(
            """
            update crm_master
            set handoff_required = true,
                handoff_status = 'draft',
                handoff_created_date = coalesce(handoff_created_date, :as_of),
                sales_handoff_summary = :summary,
                handoff_stakeholders = cast(:stakeholders as jsonb),
                implementation_requirements = cast(:impl_reqs as jsonb),
                implementation_risks = cast(:risks as jsonb),
                implementation_timeline = :timeline,
                delivery_commitments = cast(:commitments as jsonb),
                onboarding_checklist = cast(:checklist as jsonb)
            where account_id = :aid
            """
        ),
        {
            "as_of": as_of,
            "summary": fields["summary"],
            "stakeholders": json.dumps(fields["handoff_stakeholders"]),
            "impl_reqs": json.dumps(fields["implementation_requirements"]),
            "risks": json.dumps(fields["implementation_risks"]),
            "timeline": fields["implementation_timeline"],
            "commitments": json.dumps(fields["delivery_commitments"]),
            "checklist": json.dumps(fields["onboarding_checklist"]),
            "aid": account_id,
        },
    )
    await session.commit()
    payload = await get_handoff(session, account_id)
    payload["notice"] = "Handoff pack generated as draft. Approve when ready for delivery discussion."
    return payload


async def approve_handoff(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = await _load(session, account_id)
    if row.get("deal_status") != "won":
        raise DealNotWonError()
    status = _normalize_status(row.get("handoff_status"))
    if status not in {"draft", "approved"}:
        # allow pending/in_progress from seed as draft-equivalent
        if (row.get("handoff_status") or "").lower() not in {
            "draft",
            "pending",
            "in_progress",
            "approved",
            "completed",
        }:
            raise HandoffNotDraftError()
    if not row.get("sales_handoff_summary") and not _list(row.get("onboarding_checklist")):
        raise ValidationAppError("Generate a handoff pack before approving.")

    await session.execute(
        text(
            "update crm_master set handoff_status = 'approved' where account_id = :aid"
        ),
        {"aid": account_id},
    )
    await session.commit()
    payload = await get_handoff(session, account_id)
    payload["notice"] = (
        "Handoff approved for delivery discussion. Nothing was emailed or ticketed."
    )
    return payload
