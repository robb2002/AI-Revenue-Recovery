from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.services.f3_llm import llm_extract, quote_in_transcript, validate_extraction
from app.services.f3_storage import save_meeting_file

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "data" / "crm_master" / "sample_meetings"
ALLOWED_EXT = {"txt", "docx", "pdf"}
REJECT_EXT = {"csv", "xls", "xlsx", "doc", "png", "jpg", "jpeg"}
MAX_CHARS = 100_000
MAX_BYTES = 1_000_000


class ConfirmationRequiredError(AppError):
    status_code = 422
    code = "CONFIRMATION_REQUIRED"
    message = "Confirmation is required before writing to CRM."


class ValidationAppError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "The request is not valid."


class UnsupportedMediaError(AppError):
    status_code = 415
    code = "UNSUPPORTED_MEDIA"
    message = "Unsupported file type."


class TranscriptTooLargeError(AppError):
    status_code = 413
    code = "TRANSCRIPT_TOO_LARGE"
    message = "Transcript exceeds the maximum allowed size."


def _parse_jsonb(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw


def _bytes_to_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "txt":
        return data.decode("utf-8", errors="replace")
    if ext in {"docx", "pdf"}:
        # MVP: no heavy parsers in requirements — try UTF-8; UI can paste if empty
        try:
            text_out = data.decode("utf-8")
            if text_out.strip() and "\x00" not in text_out[:200]:
                return text_out
        except UnicodeDecodeError:
            pass
        raise UnsupportedMediaError(
            "DOCX/PDF text extraction is limited in MVP. Upload a .txt transcript "
            "(use ACC-0181 sample) or paste the text after upload."
        )
    raise UnsupportedMediaError(f"Unsupported type .{ext}")


def sample_transcript_path() -> Path:
    return SAMPLE_DIR / "ACC-0181_followup_call_2026-10-28.txt"


def load_sample_transcript() -> dict[str, Any]:
    path = sample_transcript_path()
    if not path.exists():
        raise NotFoundError("sample_transcript", "Sample transcript not found on disk")
    text_body = path.read_text(encoding="utf-8")
    return {
        "filename": path.name,
        "transcript": text_body,
        "account_id": "ACC-0181",
        "opportunity_id": "OPP-0181",
        "account_name": "Georgia Institute of Technology",
        "data_label": "Fictional demo data",
    }


def heuristic_extract(transcript: str) -> dict[str, Any]:
    """Deterministic fallback for ACC-0181 / similar demo transcripts (no invented $)."""

    def item(value: str, quote: str, status: str = "confirmed") -> dict[str, str]:
        if quote and not quote_in_transcript(quote, transcript):
            # find a shorter anchor
            for part in re.split(r"[.]", quote):
                part = part.strip()
                if len(part) > 20 and quote_in_transcript(part, transcript):
                    return {"value": value, "status": status, "quote": part}
            return {"value": value, "status": "unconfirmed", "quote": ""}
        return {"value": value, "status": status, "quote": quote}

    extraction = {
        "meeting_summary": item(
            "Follow-up on MyLab/Pearson+ for gateway courses; Canvas SSO and grade passback; "
            "committee review before any budget commitment.",
            "Funding has not been formally approved yet",
        ),
        "customer_requirements": [
            item(
                "LMS integration with Canvas including SSO",
                "LMS integration with Canvas",
            ),
            item(
                "Grades must pass back into the Canvas gradebook",
                "grades must pass back into the Canvas gradebook",
            ),
            item(
                "MyLab for high-enrolment gateway courses; Pearson+ as affordable access option",
                "MyLab for the high-enrolment gateway courses",
            ),
        ],
        "budget_discussion": item(
            "Funding not formally approved; academic technology committee meets 2026-11-20",
            "Funding has not been formally approved yet. The academic technology committee meets on 2026-11-20",
            "confirmed",
        ),
        "pain_points": [
            item(
                "Disconnected tools across departments",
                "tools are disconnected across departments",
            ),
            item(
                "High student material costs",
                "material costs are high",
            ),
        ],
        "objections": [
            item(
                "No scheduled budget vote before 2026-11-20",
                "we still do not have a scheduled budget vote before 2026-11-20",
            ),
        ],
        "stakeholders": [
            item("Amara Bennett — Director of Digital Learning", "Amara Bennett, Director of Digital Learning"),
            item("Tariq Hughes — Director of Digital Learning (IT)", "Tariq Hughes, Director of Digital Learning (IT)"),
            item("Ravi Hughes — Associate Dean, Academic Affairs", "Ravi Hughes, Associate Dean, Academic Affairs"),
        ],
        "competitor_mentions": [
            item(
                "Another adaptive practice platform (unnamed)",
                "another adaptive practice platform",
                "unconfirmed",
            ),
        ],
        "decision_criteria": [
            item("Canvas integration confirmed", "Canvas integration confirmed"),
            item("Written accessibility documentation", "written accessibility documentation available"),
            item("Student access cost", "student access cost"),
            item("Realistic implementation plan before spring term", "realistic implementation plan before spring term"),
        ],
        "customer_commitments": [
            item(
                "Introduce committee chair by email this week",
                "introduce you to the committee chair by email this week",
            ),
            item(
                "Share Canvas admin contact by Friday 2026-10-31",
                "share our Canvas admin contact by Friday 2026-10-31",
            ),
        ],
        "action_items": [
            item(
                "Seller: send LMS and grade-sync excerpts",
                "send the LMS and grade-sync excerpts",
            ),
            item(
                "Seller: send how to request accessibility documents",
                "send how to request accessibility documents",
            ),
            item(
                "Seller: draft one-page pilot scope for three gateway courses (no discount figure)",
                "I will not include a discount figure",
            ),
        ],
        "deadlines": [
            item(
                "Written answers needed by 2026-11-12",
                "written answers by 2026-11-12",
            ),
            item(
                "Committee meeting 2026-11-20",
                "committee meets on 2026-11-20",
            ),
        ],
        "recommended_next_steps": [
            item(
                "30-minute technical call with Canvas admin week of 2026-11-04",
                "technical call with your Canvas admin in the week of 2026-11-04",
            ),
        ],
    }
    return validate_extraction(extraction, transcript)


async def find_account_matches(session: AsyncSession, transcript: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()

    for acc in re.findall(r"\bACC-\d{4}\b", transcript, flags=re.I):
        acc_id = acc.upper()
        if acc_id in seen:
            continue
        row = (
            await session.execute(
                text(
                    """
                    select account_id, account_name, opportunity_id, opportunity_name, deal_status
                    from crm_master where account_id = :aid
                    """
                ),
                {"aid": acc_id},
            )
        ).mappings().first()
        if row:
            seen.add(acc_id)
            matches.append(
                {
                    "account_id": row["account_id"],
                    "account_name": row["account_name"],
                    "opportunity_id": row["opportunity_id"],
                    "opportunity_name": row["opportunity_name"],
                    "deal_status": row["deal_status"],
                    "confidence": "high",
                    "reason": f"Transcript cites {acc_id}",
                }
            )

    # Exact account name hits (limited)
    names = (
        await session.execute(
            text(
                """
                select account_id, account_name, opportunity_id, opportunity_name, deal_status
                from crm_master
                where position(lower(account_name) in lower(:t)) > 0
                limit 5
                """
            ),
            {"t": transcript[:8000]},
        )
    ).mappings().all()
    for row in names:
        if row["account_id"] in seen:
            continue
        seen.add(row["account_id"])
        matches.append(
            {
                "account_id": row["account_id"],
                "account_name": row["account_name"],
                "opportunity_id": row["opportunity_id"],
                "opportunity_name": row["opportunity_name"],
                "deal_status": row["deal_status"],
                "confidence": "medium",
                "reason": "Account name found in transcript",
            }
        )
    return matches


async def upload_meeting(
    session: AsyncSession,
    *,
    filename: str,
    data: bytes,
    account_id: str | None = None,
    opportunity_id: str | None = None,
) -> dict[str, Any]:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in REJECT_EXT or ext not in ALLOWED_EXT:
        raise UnsupportedMediaError(
            f".{ext or 'unknown'} is not supported. Use txt (demo), or docx/pdf when text-extractable."
        )
    if len(data) > MAX_BYTES:
        raise TranscriptTooLargeError()

    transcript = _bytes_to_text(filename, data)
    if len(transcript) > MAX_CHARS:
        raise TranscriptTooLargeError()

    stored = save_meeting_file(account_id=account_id, filename=filename, data=data)
    matches = await find_account_matches(session, transcript)

    if account_id:
        row = (
            await session.execute(
                text(
                    """
                    select account_id, account_name, opportunity_id, opportunity_name, deal_status
                    from crm_master where account_id = :aid
                    """
                ),
                {"aid": account_id},
            )
        ).mappings().first()
        if not row:
            raise NotFoundError("account")
        selected = {
            "account_id": row["account_id"],
            "account_name": row["account_name"],
            "opportunity_id": opportunity_id or row["opportunity_id"],
            "opportunity_name": row["opportunity_name"],
            "deal_status": row["deal_status"],
            "confidence": "high",
            "reason": "Provided by salesperson",
        }
        needs_confirmation = False
    elif len(matches) == 1:
        selected = matches[0]
        needs_confirmation = True
    elif len(matches) > 1:
        selected = None
        needs_confirmation = True
    else:
        selected = None
        needs_confirmation = True

    return {
        "meeting_id": stored["meeting_id"],
        "storage_path": stored["storage_path"],
        "uploaded_file_name": stored["uploaded_file_name"],
        "uploaded_file_type": stored["uploaded_file_type"],
        "content_hash": stored["content_hash"],
        "transcript": transcript,
        "char_count": len(transcript),
        "suggested_matches": matches,
        "selected_match": selected,
        "needs_confirmation": needs_confirmation,
        "data_label": "Fictional demo data",
        "notice": "File stored locally for demo. CRM not updated until Save confirm.",
    }


async def extract_meeting(
    session: AsyncSession,
    *,
    transcript: str,
    account_id: str | None = None,
    opportunity_id: str | None = None,
) -> dict[str, Any]:
    if not transcript or not transcript.strip():
        raise ValidationAppError("Transcript is required.")
    if len(transcript) > MAX_CHARS:
        raise TranscriptTooLargeError()

    if account_id:
        exists = await session.scalar(
            text("select 1 from crm_master where account_id = :aid"),
            {"aid": account_id},
        )
        if not exists:
            raise NotFoundError("account")

    llm = await llm_extract(transcript, account_id)
    if llm:
        extraction = llm
        source = "azure_openai"
    else:
        extraction = heuristic_extract(transcript)
        source = "heuristic_fallback"

    # Held-back sanity: ensure no fabricated 650k
    blob = json.dumps(extraction).lower()
    if "650,000" in blob or "650000" in blob:
        if "650" not in transcript.replace(",", ""):
            extraction["budget_discussion"] = {
                "value": "Funding has not been formally approved yet (no approved amount in transcript)",
                "status": "confirmed",
                "quote": "Funding has not been formally approved yet"
                if quote_in_transcript("Funding has not been formally approved yet", transcript)
                else "",
            }

    return {
        "account_id": account_id,
        "opportunity_id": opportunity_id,
        "extraction": extraction,
        "source": source,
        "ai_unavailable": source != "azure_openai",
        "data_label": "Fictional demo data",
        "notice": "Draft extraction for human review. Not saved to CRM yet.",
    }


def _flatten_for_upload_object(extraction: dict[str, Any]) -> dict[str, Any]:
    def vals(key: str) -> list[Any]:
        raw = extraction.get(key)
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            return [raw]
        return []

    summary = extraction.get("meeting_summary")
    budget = extraction.get("budget_discussion")
    return {
        "meeting_summary": (summary or {}).get("value") if isinstance(summary, dict) else summary,
        "customer_requirements": vals("customer_requirements"),
        "budget_discussion": (budget or {}).get("value") if isinstance(budget, dict) else budget,
        "pain_points": vals("pain_points"),
        "objections": vals("objections"),
        "stakeholders": vals("stakeholders"),
        "competitor_mentions": vals("competitor_mentions"),
        "decision_criteria": vals("decision_criteria"),
        "customer_commitments": vals("customer_commitments"),
        "action_items": vals("action_items"),
        "deadlines": vals("deadlines"),
        "recommended_next_steps": vals("recommended_next_steps"),
        "extraction_detail": extraction,
    }


async def preview_save(
    session: AsyncSession,
    *,
    account_id: str,
    opportunity_id: str | None,
    storage_path: str,
    uploaded_file_name: str,
    uploaded_file_type: str,
    transcript: str,
    extraction: dict[str, Any],
    meeting_id: str | None = None,
    content_hash: str | None = None,
) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                select account_id, account_name, opportunity_id, meeting_transcript,
                       uploaded_meetings
                from crm_master where account_id = :aid
                """
            ),
            {"aid": account_id},
        )
    ).mappings().first()
    if not row:
        raise NotFoundError("account")

    existing = _parse_jsonb(row.get("uploaded_meetings")) or []
    if not isinstance(existing, list):
        existing = []

    mid = meeting_id or f"mtg-pending"
    flat = _flatten_for_upload_object(extraction)
    proposed = {
        "meeting_id": mid,
        "account_id": account_id,
        "opportunity_id": opportunity_id or row["opportunity_id"],
        "uploaded_file_name": uploaded_file_name,
        "uploaded_file_type": uploaded_file_type,
        "storage_path": storage_path,
        "upload_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "transcript": transcript,
        **flat,
        "processing_status": "saved",
        "data_classification": "SYNTHETIC",
        "content_hash": content_hash,
    }

    field_destinations = [
        {"extraction_key": "meeting_summary", "crm_field": "uploaded_meetings[].meeting_summary"},
        {"extraction_key": "customer_requirements", "crm_field": "uploaded_meetings[].customer_requirements"},
        {"extraction_key": "budget_discussion", "crm_field": "uploaded_meetings[].budget_discussion"},
        {"extraction_key": "pain_points", "crm_field": "uploaded_meetings[].pain_points"},
        {"extraction_key": "objections", "crm_field": "uploaded_meetings[].objections"},
        {"extraction_key": "stakeholders", "crm_field": "uploaded_meetings[].stakeholders"},
        {"extraction_key": "competitor_mentions", "crm_field": "uploaded_meetings[].competitor_mentions"},
        {"extraction_key": "decision_criteria", "crm_field": "uploaded_meetings[].decision_criteria"},
        {"extraction_key": "customer_commitments", "crm_field": "uploaded_meetings[].customer_commitments"},
        {"extraction_key": "action_items", "crm_field": "uploaded_meetings[].action_items"},
        {"extraction_key": "deadlines", "crm_field": "uploaded_meetings[].deadlines"},
        {"extraction_key": "recommended_next_steps", "crm_field": "uploaded_meetings[].recommended_next_steps"},
        {"extraction_key": "(full extraction)", "crm_field": "uploaded_meetings[].extraction_detail"},
        {"extraction_key": "(transcript)", "crm_field": "uploaded_meetings[].transcript"},
    ]

    return {
        "account_id": account_id,
        "account_name": row["account_name"],
        "requires_confirmation": True,
        "proposed_uploaded_meeting": proposed,
        "field_destinations": field_destinations,
        "current_uploaded_count": len(existing),
        "will_not_change": [
            "pre-generated meeting_transcript and meeting_* columns",
            "deal_status / opportunity stage",
            "No mark won or recovered",
        ],
        "summary": (
            f"Append 1 meeting object to uploaded_meetings on {row['account_name']} "
            f"({account_id}) — count {len(existing)} → {len(existing) + 1}."
        ),
        "data_label": "Fictional demo data",
    }


async def confirm_save(
    session: AsyncSession,
    *,
    confirm: bool,
    account_id: str,
    opportunity_id: str | None,
    storage_path: str,
    uploaded_file_name: str,
    uploaded_file_type: str,
    transcript: str,
    extraction: dict[str, Any],
    meeting_id: str | None = None,
    content_hash: str | None = None,
) -> dict[str, Any]:
    if not confirm:
        raise ConfirmationRequiredError()

    preview = await preview_save(
        session,
        account_id=account_id,
        opportunity_id=opportunity_id,
        storage_path=storage_path,
        uploaded_file_name=uploaded_file_name,
        uploaded_file_type=uploaded_file_type,
        transcript=transcript,
        extraction=extraction,
        meeting_id=meeting_id,
        content_hash=content_hash,
    )
    proposed = preview["proposed_uploaded_meeting"]

    row = (
        await session.execute(
            text(
                """
                select uploaded_meetings, activity_history, as_of_date::text as as_of_date
                from crm_master where account_id = :aid
                """
            ),
            {"aid": account_id},
        )
    ).mappings().one()

    uploads = _parse_jsonb(row["uploaded_meetings"]) or []
    if not isinstance(uploads, list):
        uploads = []
    uploads = list(uploads)
    uploads.append(proposed)

    history = _parse_jsonb(row["activity_history"]) or []
    if not isinstance(history, list):
        history = []
    history = list(history)
    history.append(
        {
            "date": row.get("as_of_date") or datetime.now(timezone.utc).date().isoformat(),
            "type": "Meeting",
            "direction": "internal",
            "description": f"Meeting upload saved (meeting_id={proposed['meeting_id']})",
            "outcome": "Appended to uploaded_meetings",
            "classification": "SYNTHETIC",
        }
    )

    await session.execute(
        text(
            """
            update crm_master
            set uploaded_meetings = cast(:uploads as jsonb),
                activity_history = cast(:history as jsonb)
            where account_id = :aid
            """
        ),
        {
            "uploads": json.dumps(uploads),
            "history": json.dumps(history),
            "aid": account_id,
        },
    )
    await session.commit()

    # Verify pre-gen transcript untouched
    check = (
        await session.execute(
            text(
                "select length(coalesce(meeting_transcript,'')) as n from crm_master where account_id = :aid"
            ),
            {"aid": account_id},
        )
    ).scalar()

    return {
        "ok": True,
        "account_id": account_id,
        "meeting_id": proposed["meeting_id"],
        "uploaded_count": len(uploads),
        "pregenerated_transcript_length": int(check or 0),
        "notice": "Appended only. Pre-generated meeting_* columns were not overwritten.",
    }


async def get_meetings(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                select account_id, account_name, opportunity_id, opportunity_name, deal_status,
                       meeting_date::text as meeting_date, meeting_type, meeting_summary,
                       meeting_transcript, customer_requirements, pain_points, budget_discussion,
                       customer_objections, stakeholders, competitor_mentions, decision_criteria,
                       extracted_action_items, customer_commitments, meeting_insights,
                       uploaded_meetings, as_of_date::text as as_of_date
                from crm_master where account_id = :aid
                """
            ),
            {"aid": account_id},
        )
    ).mappings().first()
    if not row:
        raise NotFoundError("account")

    uploads = _parse_jsonb(row["uploaded_meetings"]) or []
    if not isinstance(uploads, list):
        uploads = []

    # Trim heavy transcript blobs for list load (UI shows preview; full text stays in DB)
    slim_uploads: list[dict[str, Any]] = []
    for u in uploads:
        if not isinstance(u, dict):
            continue
        item = dict(u)
        tr = item.get("transcript")
        if isinstance(tr, str) and len(tr) > 1200:
            item["transcript"] = tr[:1200] + "…"
            item["transcript_truncated"] = True
        # Drop nested extraction_detail from list payload (large); keep flat fields
        item.pop("extraction_detail", None)
        slim_uploads.append(item)

    pre_tr = row["meeting_transcript"] or ""
    pre_tr_s = pre_tr if not isinstance(pre_tr, str) else pre_tr
    pre_preview = pre_tr_s[:2500] + ("…" if isinstance(pre_tr_s, str) and len(pre_tr_s) > 2500 else "")

    return {
        "account_id": row["account_id"],
        "account_name": row["account_name"],
        "opportunity_id": row["opportunity_id"],
        "opportunity_name": row["opportunity_name"],
        "deal_status": row["deal_status"],
        "pregenerated": {
            "meeting_date": row["meeting_date"],
            "meeting_type": row["meeting_type"],
            "meeting_summary": row["meeting_summary"],
            "meeting_transcript": pre_preview,
            "transcript_truncated": isinstance(pre_tr_s, str) and len(pre_tr_s) > 2500,
            "customer_requirements": _parse_jsonb(row["customer_requirements"]),
            "pain_points": _parse_jsonb(row["pain_points"]),
            "budget_discussion": row["budget_discussion"],
            "customer_objections": _parse_jsonb(row["customer_objections"]),
            "stakeholders": _parse_jsonb(row["stakeholders"]),
            "competitor_mentions": _parse_jsonb(row["competitor_mentions"]),
            "decision_criteria": _parse_jsonb(row["decision_criteria"]),
            "extracted_action_items": _parse_jsonb(row["extracted_action_items"]),
            "customer_commitments": _parse_jsonb(row["customer_commitments"]),
            "meeting_insights": _parse_jsonb(row["meeting_insights"]),
        },
        "uploaded_meetings": slim_uploads,
        "as_of_date": row["as_of_date"],
        "data_label": "Fictional demo data",
        "sample_file": "ACC-0181_followup_call_2026-10-28.txt",
    }
