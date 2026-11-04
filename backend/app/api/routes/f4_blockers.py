from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, SessionDep
from app.ai import kb_indexer
from app.services import f4_blockers as svc

router = APIRouter(tags=["f4-blockers"])


class AnswerBody(BaseModel):
    question: str


@router.get("/accounts/{account_id}/blocker")
async def get_blocker(account_id: str, _user: CurrentUserDep, session: SessionDep) -> dict:
    return await svc.get_blocker(session, account_id)


@router.post("/accounts/{account_id}/blocker/answer")
async def answer_blocker(
    account_id: str, body: AnswerBody, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.answer_blocker(session, account_id, body.question)


@router.post("/blocker-answers/{answer_id}/approve")
async def approve_answer(answer_id: str, _user: CurrentUserDep, session: SessionDep) -> dict:
    return await svc.set_answer_state(session, answer_id, "approved")


@router.post("/blocker-answers/{answer_id}/reject")
async def reject_answer(answer_id: str, _user: CurrentUserDep, session: SessionDep) -> dict:
    return await svc.set_answer_state(session, answer_id, "rejected")


@router.get("/knowledge/documents")
async def knowledge_documents(_user: CurrentUserDep, session: SessionDep) -> dict:
    return await kb_indexer.list_documents(session)


@router.post("/knowledge/index")
async def knowledge_index(_user: CurrentUserDep, session: SessionDep) -> dict:
    return await kb_indexer.index_bundled_kb(session)


@router.post("/knowledge/upload")
async def knowledge_upload(
    _user: CurrentUserDep,
    session: SessionDep,
    file: UploadFile = File(...),
    account_id: str | None = Form(None),
    title: str | None = Form(None),
) -> dict:
    data = await file.read()
    return await kb_indexer.upload_knowledge_document(
        session,
        filename=file.filename or "upload.txt",
        data=data,
        account_id=account_id,
        title=title,
    )
