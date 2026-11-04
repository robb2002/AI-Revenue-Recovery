"""F2 LLM — explain stored risk score only. Cannot change the number."""

from __future__ import annotations

from typing import Any

from app.ai.azure_openai import AzureChatClient

EXPLAIN_SYSTEM = """You explain a stored revenue-risk score for a salesperson.
Return JSON only:
{"interpretation":"...","recommended_action":"..."}.
Rules:
- Use ONLY the supplied score, factors, and CRM facts. Do not invent numbers, blockers, or dates.
- Do not change or restate a different score than the one given.
- Never say will close, guaranteed, is lost (unless quoting stored deal_status), or recovered revenue.
- Prefer "at risk", "may need attention", "recommended action".
- At-risk pipeline value is not lost revenue.
"""


async def llm_explain_risk(row: dict[str, Any], computed: dict[str, Any]) -> dict[str, str] | None:
    client = AzureChatClient()
    if not client.configured:
        return None
    factors = computed.get("factors") or []
    factor_lines = "\n".join(
        f"- {f.get('label')}: {f.get('points')}/{f.get('max_points')} — {f.get('detail')}"
        for f in factors
    )
    user = (
        f"account_name: {row.get('account_name')}\n"
        f"deal_status: {row.get('deal_status')}\n"
        f"opportunity_stage: {row.get('opportunity_stage')}\n"
        f"deal_value: {row.get('deal_value')}\n"
        f"revenue_risk_score: {computed.get('revenue_risk_score')}\n"
        f"risk_category: {computed.get('risk_category')}\n"
        f"inactivity_days: {computed.get('days_inactive')}\n"
        f"blocker_category: {row.get('blocker_category')}\n"
        f"blocker_severity: {row.get('blocker_severity')}\n"
        f"recommended_next_action: {row.get('recommended_next_action')}\n"
        f"risk_reason: {row.get('risk_reason') or computed.get('risk_reason')}\n"
        f"factors:\n{factor_lines}\n"
    )
    result = await client.chat_json(system=EXPLAIN_SYSTEM, user=user, temperature=0.2)
    if not result:
        return None
    interpretation = str(result.get("interpretation") or "").strip()
    action = str(result.get("recommended_action") or "").strip()
    if not interpretation or not action:
        return None
    lowered = f"{interpretation}\n{action}".lower()
    for banned in ("will close", "guaranteed", "recovered revenue", "is recovered"):
        if banned in lowered:
            return None
    return {"interpretation": interpretation, "recommended_action": action}
