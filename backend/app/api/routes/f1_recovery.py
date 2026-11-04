from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, SessionDep
from app.services import f1_recovery as svc

router = APIRouter(tags=["f1-recovery"])


class DraftPatch(BaseModel):
    subject: str | None = None
    body: str | None = None


class ConfirmBody(BaseModel):
    confirm: bool = False
    source: str = "draft"
    gmail_message_id: str | None = None


@router.get("/recovery")
async def recovery_list(
    _user: CurrentUserDep,
    session: SessionDep,
    eligibility: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    return await svc.list_recovery(
        session, eligibility=eligibility, limit=limit, offset=offset
    )


@router.get("/accounts/{account_id}/recovery")
async def recovery_detail(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.get_recovery_detail(session, account_id)


@router.post("/accounts/{account_id}/drafts/reengagement")
async def generate_draft(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.generate_reengagement(session, account_id)


@router.patch("/accounts/{account_id}/drafts/reengagement")
async def patch_draft(
    account_id: str, body: DraftPatch, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.patch_reengagement(session, account_id, body.subject, body.body)


@router.post("/accounts/{account_id}/drafts/reengagement/approve")
async def approve_draft(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.set_draft_state(session, account_id, "approved")


@router.post("/accounts/{account_id}/drafts/reengagement/reject")
async def reject_draft(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.set_draft_state(session, account_id, "rejected")


@router.get("/gmail/status")
async def gmail_status(_user: CurrentUserDep) -> dict:
    return {
        "connected": False,
        "mode": "fixture",
        "message": "Live Gmail OAuth not configured — Sync Gmail returns demo fixtures.",
    }


@router.post("/accounts/{account_id}/gmail/sync")
async def gmail_sync(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    detail = await svc.get_recovery_detail(session, account_id)
    return svc.sync_gmail_fixtures(account_id, detail.get("contact_email"))


@router.get("/accounts/{account_id}/gmail/thread")
async def gmail_thread(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    detail = await svc.get_recovery_detail(session, account_id)
    cached = detail.get("gmail_thread")
    if cached:
        return cached
    return {
        "account_id": account_id,
        "source": "none",
        "new_messages": [],
        "previous_messages": [],
        "message": "Click Sync Gmail to load the demo thread fixtures.",
    }


@router.get("/accounts/{account_id}/crm-log/preview")
async def crm_log_preview(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.preview_crm_log(session, account_id)


@router.post("/accounts/{account_id}/crm-log/confirm")
async def crm_log_confirm(
    account_id: str, body: ConfirmBody, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.confirm_crm_log(session, account_id, body.confirm)


@router.post("/accounts/{account_id}/reopen")
async def reopen(
    account_id: str, body: ConfirmBody, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.reopen(session, account_id, body.confirm)
