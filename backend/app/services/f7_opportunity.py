"""F7 — correlate validated signals into potential opportunities + rules score."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

SIGNAL_TYPES = {
    "procurement",
    "technology_initiative",
    "leadership_change",
    "funding_budget",
    "strategic_announcement",
    "competitor_vendor",
    "contract_renewal",
}

# Rules own the integer — AI never sets this
WEIGHTS = {
    "base_pair": 35,
    "per_extra_signal": 10,
    "type_diversity": 12,
    "procurement_or_funding": 18,
    "fresh_signal": 10,
    "dated_evidence": 8,
    "max": 100,
}


def score_opportunity(
    signals: list[dict[str, Any]], *, as_of: date | None = None
) -> tuple[int, list[dict[str, Any]]]:
    as_of = as_of or date(2026, 11, 4)
    factors: list[dict[str, Any]] = []
    score = 0

    n = len(signals)
    if n >= 2:
        score += WEIGHTS["base_pair"]
        factors.append(
            {
                "key": "correlated_signals",
                "label": f"{n} correlated validated signals",
                "points": WEIGHTS["base_pair"],
            }
        )
        extra = min(3, n - 2) * WEIGHTS["per_extra_signal"]
        if extra:
            score += extra
            factors.append(
                {
                    "key": "extra_signals",
                    "label": "Additional validated signals",
                    "points": extra,
                }
            )

    types = {s.get("signal_type") for s in signals if s.get("signal_type") in SIGNAL_TYPES}
    if len(types) >= 2:
        score += WEIGHTS["type_diversity"]
        factors.append(
            {
                "key": "type_diversity",
                "label": f"Signal type diversity ({len(types)} types)",
                "points": WEIGHTS["type_diversity"],
            }
        )

    if types & {"procurement", "funding_budget"}:
        score += WEIGHTS["procurement_or_funding"]
        factors.append(
            {
                "key": "procurement_funding",
                "label": "Procurement or funding/budget signal present",
                "points": WEIGHTS["procurement_or_funding"],
            }
        )

    fresh = 0
    dated = 0
    for s in signals:
        for ev in s.get("evidence") or []:
            pub = ev.get("published_date")
            if pub and pub != "unavailable":
                dated += 1
                try:
                    d = date.fromisoformat(str(pub)[:10])
                    if (as_of - d).days <= 400:
                        fresh += 1
                except ValueError:
                    pass
    if fresh:
        score += WEIGHTS["fresh_signal"]
        factors.append(
            {
                "key": "freshness",
                "label": "At least one recent dated public snippet",
                "points": WEIGHTS["fresh_signal"],
            }
        )
    if dated:
        score += WEIGHTS["dated_evidence"]
        factors.append(
            {
                "key": "dated_evidence",
                "label": "Evidence includes a published date",
                "points": WEIGHTS["dated_evidence"],
            }
        )

    score = max(0, min(WEIGHTS["max"], score))
    return score, factors


def correlate_opportunities(
    target: dict[str, Any], signals: list[dict[str, Any]], *, as_of: date | None = None
) -> list[dict[str, Any]]:
    """Default: need ≥2 validated signals to form a potential opportunity."""
    validated = [s for s in signals if (s.get("evidence") or []) and s.get("signal_type")]
    if len(validated) < 2:
        return []

    score, factors = score_opportunity(validated, as_of=as_of)
    types = sorted({s.get("signal_type") for s in validated if s.get("signal_type")})
    title = (
        f"Potential learning/tech opportunity — {target.get('name')}"
        if "technology_initiative" in types or "strategic_announcement" in types
        else f"Potential opportunity — {target.get('name')}"
    )
    return [
        {
            "title": title,
            "summary": (
                "Potential opportunity only — based on correlated public signals. "
                "This is not a prediction that an RFP will happen or that a deal will close."
            ),
            "score": score,
            "factors": factors,
            "signal_ids": [s["signal_id"] for s in validated if s.get("signal_id")],
            "signal_types": types,
            "status": "potential",
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
    ]


def rules_explanation(opportunity: dict[str, Any]) -> dict[str, Any]:
    facts = [
        {
            "layer": "fact",
            "text": f"Rules score is {opportunity.get('score')}/100 from documented factors.",
        }
    ]
    for f in opportunity.get("factors") or []:
        facts.append(
            {
                "layer": "fact",
                "text": f"{f.get('label')}: {f.get('points')} points.",
            }
        )
    return {
        "facts": facts,
        "interpretation": {
            "text": (
                "These public signals may be worth reviewing together as a potential opportunity. "
                "They do not prove an RFP or pipeline commitment."
            )
        },
        "recommended_action": {
            "text": (
                "Verify the cited pages, then decide whether to research further or "
                "open Lead Recovery if the account is already lost/inactive."
            )
        },
        "source": "rules",
    }
