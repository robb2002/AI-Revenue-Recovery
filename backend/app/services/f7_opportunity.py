"""F7 — correlate validated signals → potential opportunity + rules score (SIS-shaped factors)."""

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

EDTECH_TERMS = (
    "assessment",
    "testing",
    "lms",
    "learning",
    "online learning",
    "student information",
    "digital transformation",
    "modernization",
    "ai fluency",
    "edtech",
)


def _band(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    if score >= 25:
        return "low"
    return "monitor"


def score_opportunity(
    signals: list[dict[str, Any]], *, as_of: date | None = None
) -> tuple[int, list[dict[str, Any]]]:
    """Deterministic 0–100 with SIS-aligned factor keys (AI never sets the integer)."""
    as_of = as_of or date(2026, 11, 4)
    factors: list[dict[str, Any]] = []
    types = {s.get("signal_type") for s in signals if s.get("signal_type") in SIGNAL_TYPES}

    procurement = _procurement_relevance(types)
    related = _related_signal_strength(types)
    snippets = " ".join(
        (e.get("snippet") or "")
        for s in signals
        for e in (s.get("evidence") or [])
    )
    edtech = _edtech_relevance(snippets)
    recency = _recency(signals, today=as_of)
    reliability = _source_reliability(signals)

    def add(key: str, label: str, points: int, max_points: int, detail: str) -> None:
        factors.append(
            {
                "key": key,
                "label": label,
                "points": points,
                "max_points": max_points,
                "detail": detail,
            }
        )

    add(
        "procurement_relevance",
        "Procurement relevance",
        procurement,
        30,
        "Procurement / contract / funding types raise attention (not an RFP prediction).",
    )
    add(
        "related_signal_strength",
        "Related signal strength",
        related,
        25,
        f"{len(types)} distinct validated signal type(s) correlated.",
    )
    add(
        "assessment_edtech_relevance",
        "Assessment / EdTech relevance",
        edtech,
        20,
        "Learning, LMS, assessment, or digital terms in evidence snippets.",
    )
    add(
        "recency",
        "Recency",
        recency,
        15,
        "Newer published evidence scores higher vs demo as-of date.",
    )
    add(
        "source_reliability",
        "Source reliability",
        reliability,
        10,
        "Official website evidence URLs preferred.",
    )

    score = max(0, min(100, procurement + related + edtech + recency + reliability))
    return score, factors


def _procurement_relevance(types: set[str]) -> int:
    if "procurement" in types or "contract_renewal" in types:
        return 30
    if "funding_budget" in types:
        return 18
    soft = {
        "technology_initiative",
        "leadership_change",
        "strategic_announcement",
        "competitor_vendor",
    }
    if types and types <= soft:
        return 8
    return 0


def _related_signal_strength(types: set[str]) -> int:
    n = len(types)
    if n < 2:
        return 0
    points = 8 + 6 * (n - 2)
    return min(25, points)


def _edtech_relevance(text: str) -> int:
    lower = text.lower()
    hits = sum(1 for term in EDTECH_TERMS if term in lower)
    if hits <= 0:
        return 0
    if hits <= 2:
        return 10
    return 20


def _recency(signals: list[dict[str, Any]], *, today: date) -> int:
    dates: list[date] = []
    for s in signals:
        for ev in s.get("evidence") or []:
            pub = ev.get("published_date")
            if not pub or pub == "unavailable":
                continue
            try:
                dates.append(date.fromisoformat(str(pub)[:10]))
            except ValueError:
                continue
    if not dates:
        return 0
    age = (today - max(dates)).days
    if age <= 30:
        return 15
    if age <= 90:
        return 10
    if age <= 180:
        return 5
    return 0


def _source_reliability(signals: list[dict[str, Any]]) -> int:
    best = 0
    for s in signals:
        for ev in s.get("evidence") or []:
            url = ev.get("url") or ""
            if url.startswith("https://"):
                best = max(best, 6)  # official_website-equivalent
            elif url.startswith("http"):
                best = max(best, 3)
    return best


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
            "score_band": _band(score),
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
                "text": f"{f.get('label')}: {f.get('points')}/{f.get('max_points')} points.",
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
