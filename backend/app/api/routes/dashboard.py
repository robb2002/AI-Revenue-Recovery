from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import CurrentUserDep, SessionDep
from app.core.config import get_settings

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(_user: CurrentUserDep, session: SessionDep) -> dict:
    settings = get_settings()
    result = await session.execute(
        text(
            """
            select
              coalesce(sum(deal_value) filter (where deal_status in ('open','stalled')), 0) as pipeline_open,
              coalesce(sum(deal_value) filter (
                where deal_status in ('open','stalled') and risk_category = 'high'
              ), 0) as at_risk,
              count(*) filter (where recovery_eligibility in ('eligible','review')) as recovery_eligible,
              count(*) filter (
                where deal_status in ('open','stalled') and risk_category = 'high'
              ) as high_risk,
              count(*) filter (where blocker_detected is true and coalesce(blocker_status,'') <> 'resolved') as open_blockers,
              count(*) filter (where deal_status = 'won' and coalesce(handoff_required, false)) as handoffs,
              max(as_of_date)::text as as_of
            from crm_master
            """
        )
    )
    row = result.one()
    as_of = row.as_of or settings.demo_as_of_date

    briefing_rows = (
        await session.execute(
            text(
                """
                select account_id, account_name, risk_category, recommended_next_action, revenue_risk_score
                from crm_master
                where deal_status in ('open','stalled') and risk_category = 'high'
                order by revenue_risk_score desc nulls last
                limit 5
                """
            )
        )
    ).mappings().all()

    briefing = [
        {
            "account_id": r["account_id"],
            "title": r["account_name"],
            "reason": f"High risk score {r['revenue_risk_score']}",
            "recommended_action": r["recommended_next_action"] or "Review deal risk evidence",
            "priority": "high",
            "feature_key": "risk_prioritizer",
            "href": f"/risk/{r['account_id']}",
        }
        for r in briefing_rows
    ]

    return {
        "as_of_date": as_of,
        "pipeline_open_usd": float(row.pipeline_open or 0),
        "at_risk_usd": float(row.at_risk or 0),
        "at_risk_note": "At-risk value is not lost revenue.",
        "recovery_eligible_count": int(row.recovery_eligible or 0),
        "high_risk_count": int(row.high_risk or 0),
        "open_blocker_count": int(row.open_blockers or 0),
        "won_pending_handoff_count": int(row.handoffs or 0),
        "briefing": briefing,
        "data_label": "Fictional demo data",
    }
