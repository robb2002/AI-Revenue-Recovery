from fastapi import APIRouter

from app.api.routes import (
    accounts,
    dashboard,
    data,
    f1_recovery,
    f2_risk,
    f3_meetings,
    f4_blockers,
    f5_drafts,
    f6_handoff,
    f7_signal_scout,
    health,
    me,
)

public_router = APIRouter(prefix='/api/v1')
public_router.include_router(health.router)

protected_router = APIRouter(prefix='/api/v1')
protected_router.include_router(me.router)
protected_router.include_router(data.router)
protected_router.include_router(accounts.router)
protected_router.include_router(dashboard.router)
protected_router.include_router(f1_recovery.router)
protected_router.include_router(f2_risk.router)
protected_router.include_router(f3_meetings.router)
protected_router.include_router(f4_blockers.router)
protected_router.include_router(f5_drafts.router)
protected_router.include_router(f6_handoff.router)
protected_router.include_router(f7_signal_scout.router)
