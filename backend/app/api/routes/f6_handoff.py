from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, SessionDep
from app.services import f6_handoff as svc

router = APIRouter(tags=["f6-handoff"])


class MarkWonBody(BaseModel):
    confirm: bool = False


@router.post("/accounts/{account_id}/mark-won")
async def mark_won(
    account_id: str, body: MarkWonBody, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.mark_won(session, account_id, body.confirm)


@router.get("/accounts/{account_id}/handoff")
async def get_handoff(account_id: str, _user: CurrentUserDep, session: SessionDep) -> dict:
    return await svc.get_handoff(session, account_id)


@router.post("/accounts/{account_id}/handoff/generate")
async def generate_handoff(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.generate_handoff(session, account_id)


@router.post("/accounts/{account_id}/handoff/approve")
async def approve_handoff(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.approve_handoff(session, account_id)
