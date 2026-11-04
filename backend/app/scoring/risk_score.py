"""F2 revenue risk score — rules only (AI_RAG_DESIGN §5.3).

scoring_version: risk_v1
RISK_BAND_SOURCE for list display of pre-seeded rows: prefer stored risk_category;
recompute writes score + category from these rules.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

SCORING_VERSION = "risk_v1"
RISK_BAND_SOURCE = "stored_category"  # list UI; recompute overwrites both

# Bands after recompute (AI_RAG_DESIGN §5.3)
HIGH_MIN = 70
MEDIUM_MIN = 40


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _as_of(row: dict[str, Any]) -> date:
    return _parse_date(row.get("as_of_date")) or date(2026, 11, 4)


def _inactivity_days(row: dict[str, Any]) -> int:
    if row.get("inactivity_days") is not None:
        try:
            return max(0, int(row["inactivity_days"]))
        except (TypeError, ValueError):
            pass
    as_of = _as_of(row)
    last = _parse_date(row.get("last_activity_date"))
    if last:
        return max(0, (as_of - last).days)
    return 0


def _normalize_stage(stage: str | None) -> str:
    if not stage:
        return "prospecting"
    s = stage.lower().replace("&", " ").replace("-", " ").replace("_", " ")
    s = " ".join(s.split())
    if "security" in s or "procurement" in s:
        return "security_review"
    if "negotiat" in s:
        return "negotiation"
    if "proposal" in s:
        return "proposal"
    if "discover" in s:
        return "discovery"
    if "prospect" in s or "qualify" in s:
        return "prospecting"
    if "closed" in s:
        return "closed"
    return "prospecting"


STAGE_POINTS = {
    "security_review": 10,
    "negotiation": 7,
    "proposal": 6,
    "discovery": 3,
    "prospecting": 2,
    "closed": 0,
}


def _deal_value_points(value: float) -> tuple[int, str]:
    if value >= 200_000:
        return 25, f"${value:,.0f} (>= $200,000 tier)"
    if value >= 100_000:
        return 20, f"${value:,.0f} ($100,000-$199,999 tier)"
    if value >= 50_000:
        return 14, f"${value:,.0f} ($50,000-$99,999 tier)"
    if value >= 25_000:
        return 8, f"${value:,.0f} ($25,000-$49,999 tier)"
    return 4, f"${value:,.0f} (< $25,000 tier)"


def _inactivity_points(days: int) -> tuple[int, str]:
    if days <= 7:
        return 0, f"{days} days inactive (0-7 tier)"
    if days <= 14:
        return 8, f"{days} days inactive (8-14 tier)"
    if days <= 21:
        return 16, f"{days} days inactive (15-21 tier)"
    return 25, f"{days} days inactive (>= 22 days tier)"


def _close_proximity_points(row: dict[str, Any]) -> tuple[int, str, int | None]:
    as_of = _as_of(row)
    close = _parse_date(row.get("expected_close_date"))
    if not close:
        return 0, "No expected close date", None
    days_to_close = (close - as_of).days
    if days_to_close > 60:
        return 0, f"{days_to_close} days to close (> 60)", days_to_close
    if days_to_close >= 31:
        return 8, f"{days_to_close} days to close (31-60 tier)", days_to_close
    if days_to_close >= 15:
        return 14, f"{days_to_close} days to close (15-30 tier)", days_to_close
    label = (
        f"{days_to_close} days to close (<= 14 / overdue tier)"
        if days_to_close >= 0
        else f"{abs(days_to_close)} days past close (overdue)"
    )
    return 20, label, days_to_close


def _is_overdue(row: dict[str, Any]) -> bool:
    as_of = _as_of(row)
    for key in ("next_followup_date", "next_action_date"):
        d = _parse_date(row.get(key))
        if d is not None and d < as_of:
            return True
    return False


def _activity_list(row: dict[str, Any]) -> list[dict[str, Any]]:
    history = row.get("activity_history")
    if isinstance(history, list):
        return [h for h in history if isinstance(h, dict)]
    return []


def _documented_risk_points(row: dict[str, Any]) -> tuple[int, str, list[str]]:
    """Capped at 20 — overdue, unanswered inbound, cancelled meeting, competitor signal, blocker."""
    as_of = _as_of(row)
    points = 0
    parts: list[str] = []
    keys: list[str] = []

    if _is_overdue(row):
        points += 7
        parts.append("overdue next action (+7)")
        keys.append("overdue")

    # Unanswered inbound: inbound activity after last outbound/email without later outbound
    activities = sorted(
        _activity_list(row),
        key=lambda a: str(a.get("date") or ""),
    )
    last_inbound_idx = -1
    last_outbound_idx = -1
    for i, a in enumerate(activities):
        direction = str(a.get("direction") or "").lower()
        if direction == "inbound":
            last_inbound_idx = i
        if direction == "outbound":
            last_outbound_idx = i
    if last_inbound_idx >= 0 and last_inbound_idx > last_outbound_idx:
        points += 8
        parts.append("unanswered inbound (+8)")
        keys.append("unanswered_inbound")

    # meeting_cancelled within 30 days of as_of
    for a in activities:
        atype = str(a.get("type") or "").lower()
        if "cancel" in atype or atype == "meeting_cancelled":
            ad = _parse_date(a.get("date"))
            if ad and 0 <= (as_of - ad).days <= 30:
                points += 5
                parts.append("meeting cancelled within 30 days (+5)")
                keys.append("meeting_cancelled")
                break

    signal_type = str(row.get("signal_type") or "").lower()
    sig_date = _parse_date(row.get("signal_published_date"))
    if signal_type == "competitor_adoption" and sig_date and 0 <= (as_of - sig_date).days <= 90:
        points += 5
        parts.append("competitor_adoption signal in 90-day window (+5)")
        keys.append("competitor_signal")

    blocker_status = str(row.get("blocker_status") or "").lower()
    severity = str(row.get("blocker_severity") or "").lower()
    detected = bool(row.get("blocker_detected"))
    if detected and blocker_status in {"open", "in_progress"} and severity in {"high", "medium"}:
        points += 5
        parts.append(f"open blocker ({severity}) (+5)")
        keys.append("blocker")

    competitor = str(row.get("competitor_category") or "").strip()
    if competitor and competitor.lower() not in {"", "none", "none identified", "n/a"}:
        if "competitor_signal" not in keys:
            points += 3
            parts.append(f"competitor noted: {competitor} (+3)")
            keys.append("competitor")

    if not row.get("is_decision_maker"):
        points += 3
        parts.append("contact is not marked decision maker (+3)")
        keys.append("decision_maker")

    capped = min(20, points)
    detail = "; ".join(parts) if parts else "No documented risk signals"
    if points > 20:
        detail += f" (raw {points}, capped at 20)"
    return capped, detail, keys


def band_for_score(score: int) -> str:
    if score >= HIGH_MIN:
        return "high"
    if score >= MEDIUM_MIN:
        return "medium"
    return "low"


def compute_risk_score(row: dict[str, Any]) -> dict[str, Any]:
    """Return score, band, factors, reason sentence. Never calls a model."""
    value = float(row.get("deal_value") or 0)
    days = _inactivity_days(row)
    stage_key = _normalize_stage(row.get("opportunity_stage"))

    v_pts, v_detail = _deal_value_points(value)
    i_pts, i_detail = _inactivity_points(days)
    c_pts, c_detail, days_to_close = _close_proximity_points(row)
    s_pts = STAGE_POINTS.get(stage_key, 2)
    s_detail = f"Stage mapped to {stage_key} ({s_pts} pts)"
    d_pts, d_detail, d_keys = _documented_risk_points(row)

    factors = [
        {
            "key": "deal_value",
            "label": "Deal value",
            "points": v_pts,
            "max_points": 25,
            "detail": v_detail,
            "evidence_ids": ["crm_deal"],
        },
        {
            "key": "inactivity",
            "label": "Inactivity",
            "points": i_pts,
            "max_points": 25,
            "detail": i_detail,
            "evidence_ids": ["activity"],
        },
        {
            "key": "close_proximity",
            "label": "Close-date proximity",
            "points": c_pts,
            "max_points": 20,
            "detail": c_detail,
            "evidence_ids": ["crm_deal"],
        },
        {
            "key": "stage",
            "label": "Stage",
            "points": s_pts,
            "max_points": 10,
            "detail": s_detail,
            "evidence_ids": ["crm_deal"],
        },
        {
            "key": "documented_risk",
            "label": "Documented risk signals",
            "points": d_pts,
            "max_points": 20,
            "detail": d_detail,
            "evidence_ids": d_keys or ["crm_deal"],
        },
    ]

    score = int(sum(f["points"] for f in factors))
    category = band_for_score(score)
    top = max(factors, key=lambda f: f["points"])
    reason = (
        f"Rules score {score}/100 ({category}): top factor {top['label'].lower()} — {top['detail']}"
    )

    return {
        "revenue_risk_score": score,
        "risk_category": category,
        "risk_reason": reason,
        "factors": factors,
        "scoring_version": SCORING_VERSION,
        "days_inactive": days,
        "days_to_close": days_to_close,
        "overdue_followup": _is_overdue(row),
    }
