"""Pure completeness rules for F5 drafts — no I/O."""

from __future__ import annotations

from typing import Any


def completeness_for_row(row: dict[str, Any]) -> dict[str, Any]:
    missing: list[str] = []

    if row.get("is_decision_maker") is False:
        missing.append("Primary contact is not marked as the decision maker.")

    status = (row.get("blocker_status") or "").lower()
    if row.get("blocker_detected") and status in {"open", "in_progress"}:
        cat = row.get("blocker_category") or "blocker"
        missing.append(f"Open blocker still unresolved: {cat} ({status}).")

    reqs = row.get("customer_requirements") or []
    if isinstance(reqs, list):
        for item in reqs:
            if not isinstance(item, dict):
                continue
            st = (item.get("status") or "").lower()
            if st in {"unconfirmed", "unknown"}:
                text = item.get("requirement") or "requirement"
                missing.append(f"Requirement not confirmed: {text}")

    prefs = row.get("product_reference") or []
    if not isinstance(prefs, list) or len(prefs) == 0:
        missing.append("No product_reference claims on file — do not invent capabilities.")

    budget = (row.get("budget_discussion") or "").lower()
    if any(x in budget for x in ("not been", "waiting", "unknown", "not approved", "committee")):
        missing.append("Budget / funding is not confirmed in CRM.")

    return {"complete": len(missing) == 0, "missing": missing}
