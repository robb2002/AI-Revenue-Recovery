"""F7 — extract 7 signal types from fetched page text; snippet must appear on page."""

from __future__ import annotations

import logging
from typing import Any

from app.ai.azure_openai import AzureChatClient
from app.services.f7_page_validate import SIGNAL_TYPES

logger = logging.getLogger("app.services.f7_signal_extract")

_MAX_BODY = 8_000
_MAX_PER_PAGE = 3


async def extract_signals_from_pages(
    *,
    organization_name: str,
    pages_data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    pages_data items: url, title, text, page_category
    Returns signal dicts ready for persistence (evidence validated).
    """
    client = AzureChatClient()
    out: list[dict[str, Any]] = []
    for page in pages_data:
        text = (page.get("text") or "").strip()
        if len(text) < 80:
            continue
        candidates = await _extract_one(
            client,
            organization_name=organization_name,
            source_url=page.get("url") or "",
            title=page.get("title"),
            body_text=text[:_MAX_BODY],
        )
        for c in candidates:
            snippet = (c.get("snippet") or "").strip()
            if len(snippet) < 40:
                continue
            if not _snippet_on_page(snippet, text):
                continue
            stype = c.get("signal_type")
            if stype not in SIGNAL_TYPES:
                continue
            out.append(
                {
                    "signal_type": stype,
                    "title": (c.get("title") or stype)[:500],
                    "summary": (c.get("summary") or "")[:2000],
                    "evidence": [
                        {
                            "url": page.get("url"),
                            "published_date": c.get("published_date") or "unavailable",
                            "snippet": snippet[:240],
                        }
                    ],
                }
            )
    return out


async def _extract_one(
    client: AzureChatClient,
    *,
    organization_name: str,
    source_url: str,
    title: str | None,
    body_text: str,
) -> list[dict[str, Any]]:
    types_csv = ", ".join(SIGNAL_TYPES)
    if not client.configured:
        return _heuristic_extract(body_text, title=title, source_url=source_url)

    result = await client.chat_json(
        system=(
            "Extract EdTech sales signals from ONE document about the named organization. "
            "JSON only. Facts from the text only — no invented dates, people, vendors, or URLs. "
            "Never predict that an RFP will happen. "
            "snippet = exact contiguous copy from document_text (40–240 chars). If unsure, omit."
        ),
        user=(
            f"Org: {organization_name}\n"
            f"URL: {source_url}\n"
            f"Title: {title or ''}\n\n"
            f"signal_type MUST be one of: {types_csv}\n"
            "Map: LMS/assessment/digital learning/AI campus tech → technology_initiative; "
            "grants/budget/endowment → funding_budget; CIO/provost/tech leadership hire → "
            "leadership_change; RFP/RFI/solicitation → procurement; vendor adoption/partnership "
            "→ competitor_vendor; contract/renewal → contract_renewal; program/strategy launch → "
            "strategic_announcement.\n"
            f"Max {_MAX_PER_PAGE} distinct events. None → {{\"signals\":[]}}.\n\n"
            f'document_text:\n"""\n{body_text}\n"""\n\n'
            'JSON: {"signals":[{"signal_type":"technology_initiative","title":"<short>",'
            '"summary":"<what source stated>","snippet":"<verbatim>","published_date":'
            '"YYYY-MM-DD or omit"}]}'
        ),
        temperature=0.1,
        timeout_seconds=25.0,
    )
    if not result:
        return _heuristic_extract(body_text, title=title, source_url=source_url)
    signals = result.get("signals") or []
    return [s for s in signals if isinstance(s, dict)][:_MAX_PER_PAGE]


def _snippet_on_page(snippet: str, page_text: str) -> bool:
    if snippet in page_text:
        return True
    # Soft match on whitespace collapse
    a = " ".join(snippet.split()).lower()
    b = " ".join(page_text.split()).lower()
    return len(a) >= 40 and a[:80] in b


def _heuristic_extract(
    body_text: str, *, title: str | None, source_url: str
) -> list[dict[str, Any]]:
    """Offline / no-LLM fallback — keyword map only; still requires snippet on page."""
    lower = body_text.lower()
    rules = (
        ("procurement", ("rfp", "rfi", "solicitation", "invitation to bid", "purchasing")),
        ("funding_budget", ("grant", "budget approved", "funding", "appropriation")),
        ("leadership_change", ("appointed", "named cio", "new president", "provost")),
        ("technology_initiative", ("learning platform", "digital transformation", "ai fluency", "lms")),
        ("competitor_vendor", ("partnered with", "powered by", "selected vendor", "implementing")),
        ("contract_renewal", ("contract renewal", "renewed agreement", "multi-year contract")),
        ("strategic_announcement", ("strategic initiative", "launches", "announces program")),
    )
    for stype, hints in rules:
        for hint in hints:
            idx = lower.find(hint)
            if idx < 0:
                continue
            start = max(0, idx - 40)
            end = min(len(body_text), idx + 160)
            snippet = body_text[start:end].strip()
            if len(snippet) < 40:
                continue
            return [
                {
                    "signal_type": stype,
                    "title": title or hint.title(),
                    "summary": f"Public page mentions “{hint}” (heuristic extract; not an RFP claim).",
                    "snippet": snippet[:240],
                    "published_date": "unavailable",
                }
            ]
    return []
