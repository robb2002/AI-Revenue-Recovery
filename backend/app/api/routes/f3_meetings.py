from typing import Any

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, SessionDep
from app.services import f3_meetings as svc

router = APIRouter(tags=["f3-meetings"])


class ExtractBody(BaseModel):
    transcript: str
    account_id: str | None = None
    opportunity_id: str | None = None


class FormatSpeakersBody(BaseModel):
    transcript: str
    known_speakers: list[str] = Field(default_factory=list)


class SaveBody(BaseModel):
    confirm: bool = False
    account_id: str
    opportunity_id: str | None = None
    storage_path: str
    uploaded_file_name: str
    uploaded_file_type: str = "txt"
    transcript: str
    extraction: dict[str, Any] = Field(default_factory=dict)
    meeting_id: str | None = None
    content_hash: str | None = None


@router.get("/meetings/sample/ACC-0181")
async def sample_acc_0181(_user: CurrentUserDep) -> dict:
    return svc.load_sample_transcript()


@router.post("/meetings/upload")
async def meetings_upload(
    _user: CurrentUserDep,
    session: SessionDep,
    file: UploadFile = File(...),
    account_id: str | None = Form(None),
    opportunity_id: str | None = Form(None),
) -> dict:
    data = await file.read()
    filename = file.filename or "upload.bin"
    return await svc.upload_meeting(
        session,
        filename=filename,
        data=data,
        account_id=account_id,
        opportunity_id=opportunity_id,
    )


@router.post("/meetings/transcribe")
async def meetings_transcribe(
    _user: CurrentUserDep,
    file: UploadFile = File(...),
) -> dict:
    """Audio → text only. Does not store audio or write CRM."""
    from app.services.f3_stt import transcribe_audio

    data = await file.read()
    filename = file.filename or "audio.wav"
    return await transcribe_audio(filename=filename, data=data)


@router.post("/meetings/format-speakers")
async def meetings_format_speakers(
    body: FormatSpeakersBody, _user: CurrentUserDep
) -> dict:
    from app.services.f3_speakers import format_speakers

    return await format_speakers(
        transcript=body.transcript,
        known_speakers=body.known_speakers,
    )


@router.post("/meetings/extract")
async def meetings_extract(
    body: ExtractBody, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.extract_meeting(
        session,
        transcript=body.transcript,
        account_id=body.account_id,
        opportunity_id=body.opportunity_id,
    )


@router.post("/meetings/save/preview")
async def meetings_save_preview(
    body: SaveBody, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.preview_save(
        session,
        account_id=body.account_id,
        opportunity_id=body.opportunity_id,
        storage_path=body.storage_path,
        uploaded_file_name=body.uploaded_file_name,
        uploaded_file_type=body.uploaded_file_type,
        transcript=body.transcript,
        extraction=body.extraction,
        meeting_id=body.meeting_id,
        content_hash=body.content_hash,
    )


@router.post("/meetings/save")
async def meetings_save(
    body: SaveBody, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.confirm_save(
        session,
        confirm=body.confirm,
        account_id=body.account_id,
        opportunity_id=body.opportunity_id,
        storage_path=body.storage_path,
        uploaded_file_name=body.uploaded_file_name,
        uploaded_file_type=body.uploaded_file_type,
        transcript=body.transcript,
        extraction=body.extraction,
        meeting_id=body.meeting_id,
        content_hash=body.content_hash,
    )


@router.get("/accounts/{account_id}/meetings")
async def account_meetings(
    account_id: str, _user: CurrentUserDep, session: SessionDep
) -> dict:
    return await svc.get_meetings(session, account_id)
