from fastapi import APIRouter

from app.api.routes import accounts, dashboard, data, health, me

public_router = APIRouter(prefix='/api/v1')
public_router.include_router(health.router)

protected_router = APIRouter(prefix='/api/v1')
protected_router.include_router(me.router)
protected_router.include_router(data.router)
protected_router.include_router(accounts.router)
protected_router.include_router(dashboard.router)
