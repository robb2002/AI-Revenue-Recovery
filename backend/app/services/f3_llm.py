"""F3 LLM extraction — quotes must appear in transcript; no invented budget."""

from __future__ import annotations

import json
import re
from typing import Any

from app.ai.azure_openai import AzureChatClient

EXTRACT_SYSTEM = """You extract structured fields from a B2B sales meeting transcript.
Return JSON only with this shape:
{
  "meeting_summary": {"value":"...", "status":"confirmed|unconfirmed|unknown", "quote":"..."},
  "customer_requirements": [{"value":"...", "status":"...", "quote":"..."}],
  "budget_discussion": {"value":"...", "status":"...", "quote":"..."},
  "pain_points": [{"value":"...", "status":"...", "quote":"..."}],
  "objections": [{"value":"...", "status":"...", "quote":"..."}],
  "stakeholders": [{"value":"Name — role", "status":"...", "quote":"..."}],
  "competitor_mentions": [{"value":"...", "status":"...", "quote":"..."}],
  "decision_criteria": [{"value":"...", "status":"...", "quote":"..."}],
  "customer_commitments": [{"value":"...", "status":"...", "quote":"..."}],
  "action_items": [{"value":"...", "status":"...", "quote":"..."}],
  "deadlines": [{"value":"...", "status":"...", "quote":"..."}],
  "recommended_next_steps": [{"value":"...", "status":"...", "quote":"..."}]
}
Rules:
- Use ONLY facts in the transcript. quote MUST be a verbatim substring of the transcript.
- If budget is not approved, say so. Never invent an approved dollar amount or discount %.
- If a competitor is unnamed, status unconfirmed/unknown — do not invent a vendor name.
- status confirmed = clear explicit statement; unconfirmed = implied; unknown = not stated.
- Do not claim the deal is won, lost, recovered, or will close.
"""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def quote_in_transcript(quote: str, transcript: str) -> bool:
    if not quote or not quote.strip():
        return False
    return _norm(quote) in _norm(transcript)


def validate_extraction(extraction: dict[str, Any], transcript: str) -> dict[str, Any]:
    """Drop items whose quote is not in the transcript; strip invented approved $. """
    banned_money = re.compile(
        r"\$\s*650,?000|approved budget of|discount\s*\d+\s*%",
        re.I,
    )
    out: dict[str, Any] = {}

    def scrub_item(item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        value = str(item.get("value") or "").strip()
        quote = str(item.get("quote") or "").strip()
        status = str(item.get("status") or "unconfirmed").lower()
        if status not in {"confirmed", "unconfirmed", "unknown"}:
            status = "unconfirmed"
        if not value:
            return None
        if quote and not quote_in_transcript(quote, transcript):
            return None
        if not quote:
            status = "unconfirmed"
        # Held-back: never allow fabricated approved budget language
        if banned_money.search(value) and not banned_money.search(transcript):
            return None
        if "approved" in value.lower() and "$" in value and "not" not in value.lower():
            if "$" not in transcript or "approved" not in _norm(transcript):
                return {
                    "value": "Budget not formally approved in transcript",
                    "status": "unknown",
                    "quote": "",
                }
        return {"value": value, "status": status, "quote": quote}

    for key, raw in extraction.items():
        if key == "meeting_summary" or key == "budget_discussion":
            cleaned = scrub_item(raw if isinstance(raw, dict) else {"value": raw})
            if cleaned:
                out[key] = cleaned
            elif key == "budget_discussion":
                out[key] = {
                    "value": "No approved budget amount stated in transcript",
                    "status": "unknown",
                    "quote": "",
                }
            continue
        if isinstance(raw, list):
            items = []
            for el in raw:
                c = scrub_item(el)
                if c:
                    items.append(c)
            out[key] = items
        elif isinstance(raw, dict):
            c = scrub_item(raw)
            out[key] = c if c else []
        else:
            out[key] = []
    return out


async def llm_extract(transcript: str, account_id: str | None) -> dict[str, Any] | None:
    client = AzureChatClient()
    if not client.configured:
        return None
    user = (
        f"account_id: {account_id or 'unknown'}\n"
        f"transcript:\n{transcript[:90000]}\n"
    )
    result = await client.chat_json(system=EXTRACT_SYSTEM, user=user, temperature=0.1)
    if not result or not isinstance(result, dict):
        return None
    return validate_extraction(result, transcript)
