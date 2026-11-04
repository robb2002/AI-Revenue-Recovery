from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, SessionDep
from app.services import f7_scan as scan_svc
from app.services import f7_signal_scout as svc

router = APIRouter(prefix="/signal-scout", tags=["f7-signal-scout"])


class CreateTargetBody(BaseModel):
    account_id: str | None = None
    name: str | None = None
    website_url: str | None = None


@router.get("/targets/search")
async def search_targets(
    _user: CurrentUserDep,
    session: SessionDep,
    q: str = Query(""),
    limit: int = Query(20, ge=1, le=50),
) -> dict:
    return await svc.search_targets(session, q, limit=limit)


@router.post("/targets")
async def create_target(
    body: CreateTargetBody, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.create_target(
        session,
        account_id=body.account_id,
        name=body.name,
        website_url=body.website_url,
    )


@router.get("/targets/{target_id}")
async def get_target(target_id: str, _user: CurrentUserDep, session: SessionDep) -> dict:
    return await svc.get_target(session, target_id)


@router.post("/targets/{target_id}/scan", status_code=202)
async def start_scan(target_id: str, _user: CurrentUserDep, session: SessionDep):
    result = await scan_svc.start_scan(session, target_id)
    # Pipeline completes inside start_scan for reliable demo; still return 202
    final = await scan_svc.get_scan(session, result["scan_id"])
    return JSONResponse(
        status_code=202,
        content={
            "scan_id": result["scan_id"],
            "target_id": target_id,
            "status": final.get("status") or "completed",
            "message": result.get("message"),
        },
    )


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: str, _user: CurrentUserDep, session: SessionDep) -> dict:
    return await scan_svc.get_scan(session, scan_id)


@router.get("/targets/{target_id}/signals")
async def list_signals(target_id: str, _user: CurrentUserDep, session: SessionDep) -> dict:
    return await svc.list_signals(session, target_id)


@router.get("/targets/{target_id}/opportunities")
async def list_opportunities(
    target_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.list_opportunities(session, target_id)


@router.get("/opportunities/{opportunity_id}")
async def get_opportunity(
    opportunity_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.get_opportunity(session, opportunity_id)


@router.post("/opportunities/{opportunity_id}/explain")
async def explain_opportunity(
    opportunity_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await scan_svc.explain_opportunity(session, opportunity_id)
