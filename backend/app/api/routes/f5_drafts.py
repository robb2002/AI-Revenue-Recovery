from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, SessionDep
from app.services import f5_drafts as svc

router = APIRouter(tags=["f5-drafts"])

ALLOWED_TYPES = {"followup_email", "proposal_outline"}


class DraftPatch(BaseModel):
    subject: str | None = None
    body: str | None = None
    sections: dict[str, Any] | None = None


def _check_type(draft_type: str) -> None:
    if draft_type not in ALLOWED_TYPES:
        raise svc.ValidationAppError(
            "draft_type must be followup_email or proposal_outline."
        )


@router.get("/accounts/{account_id}/drafts")
async def get_drafts(account_id: str, _user: CurrentUserDep, session: SessionDep) -> dict:
    return await svc.get_drafts(session, account_id)


@router.post("/accounts/{account_id}/drafts/followup")
async def generate_followup(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.generate_followup(session, account_id)


@router.post("/accounts/{account_id}/drafts/proposal")
async def generate_proposal(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.generate_proposal(session, account_id)


@router.patch("/accounts/{account_id}/drafts/{draft_type}")
async def patch_draft(
    account_id: str,
    draft_type: str,
    body: DraftPatch,
    _user: CurrentUserDep,
    session: SessionDep,
) -> dict:
    _check_type(draft_type)
    return await svc.patch_draft(
        session,
        account_id,
        draft_type,
        subject=body.subject,
        body=body.body,
        sections=body.sections,
    )


@router.post("/accounts/{account_id}/drafts/{draft_type}/approve")
async def approve_draft(
    account_id: str, draft_type: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    _check_type(draft_type)
    return await svc.set_draft_state(session, account_id, draft_type, "approved")


@router.post("/accounts/{account_id}/drafts/{draft_type}/reject")
async def reject_draft(
    account_id: str, draft_type: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    _check_type(draft_type)
    return await svc.set_draft_state(session, account_id, draft_type, "rejected")
