"""F1 LLM prompts — draft + explanation. Facts only from supplied CRM fields."""

from __future__ import annotations

from typing import Any

from app.ai.azure_openai import AzureChatClient

DRAFT_SYSTEM = """You write a short B2B re-engagement email draft for a salesperson.
Return JSON only: {"subject":"...","body":"..."}.
Rules:
- Use ONLY the facts provided. Do not invent companies, prices, discounts, dates, product features, or customer quotes.
- Do not say the deal will close, is recovered, or is guaranteed.
- Professional, concise, human. Sign as the account_owner at Lumora Learning.
- Quote the lost_reason lightly if present. Mention a public signal only if provided.
"""

EXPLAIN_SYSTEM = """You explain why a lost/inactive CRM account may be worth reviewing.
Return JSON only:
{"interpretation":"...","recommended_action":"..."}.
Rules:
- interpretation = inference from supplied facts only (not a new fact).
- recommended_action = what the salesperson should consider next.
- Never say will close, guaranteed, is recovered, or recovered revenue.
- Prefer "may be worth reviewing" / "recommended action".
"""


async def llm_draft(row: dict[str, Any]) -> dict[str, str] | None:
    client = AzureChatClient()
    if not client.configured:
        return None
    user = (
        f"account_name: {row.get('account_name')}\n"
        f"opportunity_name: {row.get('opportunity_name')}\n"
        f"contact_name: {row.get('contact_name')}\n"
        f"account_owner: {row.get('account_owner')}\n"
        f"deal_status: {row.get('deal_status')}\n"
        f"lost_reason: {row.get('lost_reason')}\n"
        f"inactivity_days: {row.get('inactivity_days')}\n"
        f"as_of_date: {row.get('as_of_date')}\n"
        f"signal_title: {row.get('signal_title')}\n"
        f"signal_classification: {row.get('signal_classification')}\n"
        f"signal_description: {(row.get('signal_description') or '')[:400]}\n"
        f"recommended_next_action: {row.get('recommended_next_action')}\n"
    )
    result = await client.chat_json(system=DRAFT_SYSTEM, user=user, temperature=0.4)
    if not result:
        return None
    subject = str(result.get("subject") or "").strip()
    body = str(result.get("body") or "").strip()
    if not subject or not body:
        return None
    lowered = f"{subject}\n{body}".lower()
    for banned in ("will close", "guaranteed", "is recovered", "recovered revenue"):
        if banned in lowered:
            return None
    return {"subject": subject, "body": body}


async def llm_explanation(row: dict[str, Any]) -> dict[str, str] | None:
    client = AzureChatClient()
    if not client.configured:
        return None
    user = (
        f"account_name: {row.get('account_name')}\n"
        f"deal_status: {row.get('deal_status')}\n"
        f"lost_reason: {row.get('lost_reason')}\n"
        f"inactivity_days: {row.get('inactivity_days')}\n"
        f"last_activity_date: {row.get('last_activity_date')}\n"
        f"as_of_date: {row.get('as_of_date')}\n"
        f"signal_title: {row.get('signal_title')}\n"
        f"signal_classification: {row.get('signal_classification')}\n"
        f"signal_description: {(row.get('signal_description') or '')[:400]}\n"
        f"recommended_next_action: {row.get('recommended_next_action')}\n"
    )
    result = await client.chat_json(system=EXPLAIN_SYSTEM, user=user, temperature=0.2)
    if not result:
        return None
    interpretation = str(result.get("interpretation") or "").strip()
    action = str(result.get("recommended_action") or "").strip()
    if not interpretation or not action:
        return None
    lowered = f"{interpretation}\n{action}".lower()
    for banned in ("will close", "guaranteed", "is recovered", "recovered revenue"):
        if banned in lowered:
            return None
    return {"interpretation": interpretation, "recommended_action": action}
