"""F5 — Follow-up email + proposal outline drafts on crm_master."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.azure_openai import AzureChatClient
from app.core.errors import AppError, NotFoundError
from app.services.f5_completeness import completeness_for_row

FORBIDDEN = re.compile(
    r"\b(guaranteed|will close|send this email|recovered|discount of \$|\$\d[\d,]*)\b",
    re.I,
)

SELECT = """
select account_id, account_name, opportunity_id, opportunity_name, deal_status, deal_value,
       currency, contact_name, contact_designation, account_owner, is_decision_maker,
       product_interest, recommended_products, recommended_solution, value_proposition,
       customer_requirements, customer_requirements_summary, pain_points, customer_objections,
       decision_criteria, budget_discussion, purchase_timeline, product_reference,
       blocker_detected, blocker_category, blocker_description, blocker_status,
       meeting_summary, followup_email_subject, followup_email_body, followup_message_status,
       next_followup_recommendation, proposal_generated, proposal_title, proposal_draft,
       proposal_status, as_of_date::text as as_of_date
from crm_master
where account_id = :aid
"""


class ValidationAppError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "The request is not valid."


class StateNotEditableError(AppError):
    status_code = 409
    code = "STATE_NOT_EDITABLE"
    message = "Draft is not editable in the current state."


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return []


def _req_texts(row: dict[str, Any], *, confirmed_only: bool = False) -> list[str]:
    out: list[str] = []
    for item in _as_list(row.get("customer_requirements")):
        if not isinstance(item, dict):
            continue
        st = (item.get("status") or "").lower()
        if confirmed_only and st not in {"confirmed", ""}:
            continue
        text = (item.get("requirement") or "").strip()
        if text:
            out.append(text)
    return out


def _product_claims(row: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in _as_list(row.get("product_reference")):
        if not isinstance(item, dict):
            continue
        claim = (item.get("claim_text") or "").strip()
        if not claim:
            continue
        out.append(
            {
                "product_name": str(item.get("product_name") or "Product"),
                "claim_text": claim,
                "source_url": str(item.get("source_url") or ""),
            }
        )
    return out


def _sanitize(text: str) -> str:
    cleaned = FORBIDDEN.sub("[removed]", text or "")
    # Strip invented-looking currency if not already removed
    cleaned = re.sub(r"\$\d[\d,]*(?:\.\d+)?", "[price not stated]", cleaned)
    return cleaned


async def _load(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = (await session.execute(text(SELECT), {"aid": account_id})).mappings().first()
    if not row:
        raise NotFoundError("account")
    return dict(row)


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    draft = row.get("proposal_draft")
    if isinstance(draft, str):
        try:
            draft = json.loads(draft)
        except json.JSONDecodeError:
            draft = None
    return {
        "account_id": row["account_id"],
        "account_name": row["account_name"],
        "opportunity_name": row.get("opportunity_name"),
        "deal_status": row.get("deal_status"),
        "deal_value": row.get("deal_value"),
        "currency": row.get("currency") or "USD",
        "contact_name": row.get("contact_name"),
        "contact_designation": row.get("contact_designation"),
        "account_owner": row.get("account_owner"),
        "product_interest": row.get("product_interest"),
        "as_of_date": row.get("as_of_date"),
        "followup": {
            "subject": row.get("followup_email_subject"),
            "body": row.get("followup_email_body"),
            "status": row.get("followup_message_status") or "none",
            "next_followup_recommendation": row.get("next_followup_recommendation"),
        },
        "proposal": {
            "generated": bool(row.get("proposal_generated")),
            "title": row.get("proposal_title"),
            "draft": draft,
            "status": row.get("proposal_status") or "none",
        },
        "completeness": completeness_for_row(row),
        "notice": "Drafts stay drafts until you approve. Approval does not send email or mark the deal won.",
        "data_label": "Fictional demo data",
    }


async def get_drafts(session: AsyncSession, account_id: str) -> dict[str, Any]:
    return _payload(await _load(session, account_id))


def _build_followup(row: dict[str, Any]) -> tuple[str, str, str]:
    contact = row.get("contact_name") or "there"
    account = row.get("account_name") or "your institution"
    owner = row.get("account_owner") or "Lumora Learning"
    reqs = _req_texts(row)[:4]
    claims = _product_claims(row)[:2]
    meeting = (row.get("meeting_summary") or "").strip()
    blocker = ""
    if row.get("blocker_detected") and (row.get("blocker_status") or "").lower() in {
        "open",
        "in_progress",
    }:
        blocker = (
            f"We also noted the open {row.get('blocker_category') or 'blocker'} item "
            f"and can bring the right internal owner to the next conversation."
        )

    subject = f"Following up on {row.get('product_interest') or 'our discussion'} for {account}"
    bullets = "\n".join(f"- {r}" for r in reqs) or "- Confirm priorities from our last conversation"
    claim_lines = ""
    if claims:
        claim_lines = "\n".join(
            f"- {c['product_name']}: “{c['claim_text']}”"
            + (f" ({c['source_url']})" if c["source_url"] else "")
            for c in claims
        )
        claim_lines = f"\nRelevant product references on file:\n{claim_lines}\n"

    body = (
        f"Hi {contact},\n\n"
        f"Thank you for the time with {account}. Based on what is on record, here is a short "
        f"follow-up you can edit before sending.\n\n"
    )
    if meeting:
        body += f"From our latest notes: {meeting[:320]}\n\n"
    body += f"Priorities we heard:\n{bullets}\n"
    body += claim_lines
    if blocker:
        body += f"\n{blocker}\n"
    body += (
        "\nSuggested next step: confirm the open questions on budget / decision timing, "
        "then we can prepare a proposal outline for your review.\n\n"
        f"Best regards,\n{owner}\n\n"
        "[Draft only — not sent. Human approval required before use outside this app.]"
    )
    rec = "Send a short follow-up confirming requirements and open budget timing."
    return _sanitize(subject), _sanitize(body), rec


def _build_proposal(row: dict[str, Any]) -> dict[str, Any]:
    account = row.get("account_name") or "Account"
    product = row.get("product_interest") or "recommended solution"
    reqs = _req_texts(row, confirmed_only=True) or _req_texts(row)
    claims = _product_claims(row)
    objections = []
    for item in _as_list(row.get("customer_objections")):
        if isinstance(item, dict) and item.get("objection"):
            objections.append(str(item["objection"]))
    open_q: list[str] = []
    completeness = completeness_for_row(row)
    open_q.extend(completeness["missing"])
    if row.get("purchase_timeline"):
        open_q.append(f"Purchase timing on file: {row['purchase_timeline']}")

    solution_bits = []
    for c in claims[:3]:
        solution_bits.append(f"{c['product_name']}: {c['claim_text']}")
    proposed = (
        row.get("value_proposition")
        or (
            f"Map confirmed needs for {account} to {product}. "
            + (" ".join(solution_bits) if solution_bits else "Confirm fit with a solutions consultant.")
        )
    )

    sources = []
    for i, r in enumerate(reqs[:5], start=1):
        sources.append({"type": "requirement", "ref": f"R{i}:{r[:80]}"})
    for c in claims[:3]:
        sources.append({"type": "product_reference", "ref": c["product_name"]})
    if row.get("meeting_summary"):
        sources.append({"type": "meeting", "ref": "meeting_summary"})
    if row.get("blocker_detected"):
        sources.append({"type": "blocker", "ref": str(row.get("blocker_category") or "blocker")})

    title = f"Proposal outline: {product} for {account}"
    draft = {
        "classification": "AI_GENERATED",
        "simulated": True,
        "requires_human_approval": True,
        "status_note": "Draft. Not sent. Human review and approval required.",
        "title": title,
        "executive_summary": _sanitize(
            f"Illustrative outline for {account} covering confirmed requirements around {product}. "
            "Commercial terms are not quoted here."
        ),
        "customer_requirements": reqs[:8],
        "proposed_solution": _sanitize(str(proposed)[:1200]),
        "engagement_outline": [
            "Confirm decision-maker and evaluation criteria",
            "Address open blockers with approved documentation",
            "Align solution scope to confirmed requirements only",
            "Human-approved commercial proposal outside this app",
        ],
        "commercial_note": "Pricing requires an approved quote — not stated here.",
        "open_questions": open_q[:8] or objections[:3] or ["Confirm next stakeholder review date."],
        "assumptions": [
            "All CRM data is fictional demo data.",
            "Product statements are limited to stored product_reference claims.",
        ],
        "next_steps": [
            "Rep reviews and edits this outline",
            "Approve when ready to use outside the app",
            "Do not mark won from this draft",
        ],
        "sources_used": sources,
    }
    return draft


FOLLOWUP_SYSTEM = """You write a short B2B sales follow-up email as JSON:
{"subject":"...","body":"...","next_followup_recommendation":"..."}
Rules: Use ONLY the supplied facts. No prices, discounts, guarantees, or send claims.
Do not invent products or requirements. Keep body under 220 words. End with a draft notice."""


PROPOSAL_SYSTEM = """You refine a proposal outline JSON. Return the full outline object.
Rules: Keep commercial_note without prices. Only use supplied requirements and product claims.
No guarantees, no invented capabilities. Keep simulated=true and requires_human_approval=true."""


async def generate_followup(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = await _load(session, account_id)
    subject, body, rec = _build_followup(row)

    client = AzureChatClient()
    if client.configured:
        facts = {
            "account": row.get("account_name"),
            "contact": row.get("contact_name"),
            "requirements": _req_texts(row)[:6],
            "product_claims": _product_claims(row)[:3],
            "meeting_summary": (row.get("meeting_summary") or "")[:500],
            "blocker": {
                "category": row.get("blocker_category"),
                "status": row.get("blocker_status"),
            },
            "seed_subject": subject,
            "seed_body": body,
        }
        result = await client.chat_json(
            system=FOLLOWUP_SYSTEM,
            user=json.dumps(facts),
            temperature=0.3,
            timeout_seconds=12.0,
        )
        if result:
            subject = _sanitize(str(result.get("subject") or subject))
            body = _sanitize(str(result.get("body") or body))
            rec = str(result.get("next_followup_recommendation") or rec)

    await session.execute(
        text(
            """
            update crm_master
            set followup_email_subject = :subject,
                followup_email_body = :body,
                followup_message_status = 'draft',
                next_followup_recommendation = :rec
            where account_id = :aid
            """
        ),
        {"subject": subject, "body": body, "rec": rec, "aid": account_id},
    )
    await session.commit()
    return await get_drafts(session, account_id)


async def generate_proposal(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = await _load(session, account_id)
    draft = _build_proposal(row)

    client = AzureChatClient()
    if client.configured:
        package = {
            "seed": draft,
            "requirements": _req_texts(row)[:8],
            "product_claims": _product_claims(row)[:4],
            "objections": row.get("customer_objections"),
            "budget_discussion": row.get("budget_discussion"),
        }
        result = await client.chat_json(
            system=PROPOSAL_SYSTEM,
            user=json.dumps(package),
            temperature=0.2,
            timeout_seconds=14.0,
        )
        if isinstance(result, dict) and result.get("title"):
            # Preserve hard guardrails even if model drifts
            result["commercial_note"] = (
                result.get("commercial_note")
                or "Pricing requires an approved quote — not stated here."
            )
            if FORBIDDEN.search(json.dumps(result)):
                result = draft
            else:
                result["simulated"] = True
                result["requires_human_approval"] = True
                result["classification"] = "AI_GENERATED"
                draft = result

    title = str(draft.get("title") or f"Proposal outline for {row.get('account_name')}")
    await session.execute(
        text(
            """
            update crm_master
            set proposal_generated = true,
                proposal_title = :title,
                proposal_draft = cast(:draft as jsonb),
                proposal_status = 'draft'
            where account_id = :aid
            """
        ),
        {"title": title, "draft": json.dumps(draft), "aid": account_id},
    )
    await session.commit()
    return await get_drafts(session, account_id)


async def patch_draft(
    session: AsyncSession,
    account_id: str,
    draft_type: str,
    *,
    subject: str | None = None,
    body: str | None = None,
    sections: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = await _load(session, account_id)
    if draft_type == "followup_email":
        if (row.get("followup_message_status") or "none") != "draft":
            raise StateNotEditableError()
        new_subject = _sanitize(subject if subject is not None else row.get("followup_email_subject") or "")
        new_body = _sanitize(body if body is not None else row.get("followup_email_body") or "")
        await session.execute(
            text(
                """
                update crm_master
                set followup_email_subject = :subject,
                    followup_email_body = :body
                where account_id = :aid
                """
            ),
            {"subject": new_subject, "body": new_body, "aid": account_id},
        )
    elif draft_type == "proposal_outline":
        if (row.get("proposal_status") or "none") != "draft":
            raise StateNotEditableError()
        draft = row.get("proposal_draft") or {}
        if isinstance(draft, str):
            draft = json.loads(draft)
        if not isinstance(draft, dict):
            draft = {}
        if sections:
            for key, value in sections.items():
                draft[key] = value
        if subject is not None:
            draft["title"] = _sanitize(subject)
            title = draft["title"]
        else:
            title = row.get("proposal_title") or draft.get("title") or "Proposal outline"
        draft["commercial_note"] = "Pricing requires an approved quote — not stated here."
        await session.execute(
            text(
                """
                update crm_master
                set proposal_title = :title,
                    proposal_draft = cast(:draft as jsonb)
                where account_id = :aid
                """
            ),
            {"title": title, "draft": json.dumps(draft), "aid": account_id},
        )
    else:
        raise ValidationAppError("draft_type must be followup_email or proposal_outline.")
    await session.commit()
    return await get_drafts(session, account_id)


async def set_draft_state(
    session: AsyncSession, account_id: str, draft_type: str, state: str
) -> dict[str, Any]:
    if state not in {"approved", "rejected"}:
        raise ValidationAppError("Invalid draft state.")
    row = await _load(session, account_id)
    if draft_type == "followup_email":
        current = row.get("followup_message_status") or "none"
        if current not in {"draft", "approved", "rejected"}:
            raise ValidationAppError("Generate a follow-up draft first.")
        await session.execute(
            text(
                "update crm_master set followup_message_status = :st where account_id = :aid"
            ),
            {"st": state, "aid": account_id},
        )
    elif draft_type == "proposal_outline":
        current = row.get("proposal_status") or "none"
        if current not in {"draft", "approved", "rejected"}:
            raise ValidationAppError("Generate a proposal draft first.")
        await session.execute(
            text("update crm_master set proposal_status = :st where account_id = :aid"),
            {"st": state, "aid": account_id},
        )
    else:
        raise ValidationAppError("draft_type must be followup_email or proposal_outline.")
    await session.commit()
    payload = await get_drafts(session, account_id)
    payload["notice"] = (
        f"{'Approved' if state == 'approved' else 'Rejected'} — nothing was sent. "
        "Deal status was not changed."
    )
    return payload
