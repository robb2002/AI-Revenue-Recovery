from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, SessionDep
from app.services import f2_risk as svc

router = APIRouter(tags=["f2-risk"])


class ConfirmBody(BaseModel):
    confirm: bool = False


@router.get("/risk")
async def risk_list(
    _user: CurrentUserDep,
    session: SessionDep,
    band: str | None = None,
    deal_status: str | None = None,
    preset: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    return await svc.list_risk(
        session,
        band=band,
        deal_status=deal_status,
        preset=preset,
        limit=limit,
        offset=offset,
    )


@router.get("/accounts/{account_id}/risk")
async def risk_detail(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.get_risk_detail(session, account_id)


@router.post("/accounts/{account_id}/risk/explain")
async def risk_explain(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.explain_risk(session, account_id)


@router.post("/accounts/{account_id}/risk/recompute")
async def risk_recompute(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.recompute_and_persist(session, account_id)


@router.get("/accounts/{account_id}/risk-action/preview")
async def risk_action_preview(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.preview_action_log(session, account_id)


@router.post("/accounts/{account_id}/risk-action/confirm")
async def risk_action_confirm(
    account_id: str, body: ConfirmBody, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.confirm_action_log(session, account_id, body.confirm)
