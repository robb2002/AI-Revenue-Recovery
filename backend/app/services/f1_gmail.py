"""F1 Gmail inbox → CRM match → human approve (briefing workflow).

Live Gmail only (read-only). No fixtures / dummy rows.
Shows only sales/lead emails that match CRM and are not yet approved.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from email.utils import parseaddr
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.services.f1_recovery import ConfirmationRequiredError, ValidationAppError, _parse_history

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"

# Sales / lead relevance (hackathon demo — keep noise out of the queue)
_SALES_TERMS = {
    "lead",
    "leads",
    "sales",
    "proposal",
    "pilot",
    "demo",
    "pricing",
    "quote",
    "renewal",
    "procurement",
    "evaluation",
    "rfp",
    "contract",
    "budget",
    "follow-up",
    "followup",
    "check-in",
    "checkin",
    "reconnect",
    "revisit",
    "meeting",
    "discovery",
    "negotiation",
    "security review",
    "mylab",
    "lumora",
    "assessment",
    "learning platform",
    "ai fluency",
    "opportunity",
    "deal",
    "pipeline",
    "onboarding",
    "handoff",
}

_INBOX_CACHE: dict[str, Any] = {
    "synced_at": None,
    "mailbox_email": None,
    "items": [],
}
# Message ids approved this process (also checked against CRM activity_history)
_APPROVED_IDS: set[str] = set()


class GmailAuthError(AppError):
    status_code = 401
    code = "GMAIL_AUTH_REQUIRED"
    message = "Connect Gmail on the briefing page, then refresh inbox."


class GmailApiError(AppError):
    status_code = 502
    code = "GMAIL_API_ERROR"
    message = "Gmail API request failed."


def mailbox_status() -> dict[str, Any]:
    settings = get_settings()
    hint = (getattr(settings, "gmail_login_hint", None) or "").strip()
    cached = _INBOX_CACHE.get("mailbox_email")
    items = _INBOX_CACHE.get("items") or []
    pending = len(items)
    return {
        "connected": bool(cached),
        "mode": "live" if cached else "disconnected",
        "mailbox_email": cached or hint or None,
        "login_hint": hint or None,
        "label": "Sales mailbox" if cached else "Connect Gmail",
        "can_send": False,
        "pending_crm_approvals": pending,
        "last_synced_at": _INBOX_CACHE.get("synced_at"),
        "message": (
            "Connected · read-only. Sync pulls sales/lead emails not yet logged to CRM."
            if cached
            else "Connect sales Gmail on Briefing, then Sync Gmail inbox."
        ),
    }


def _extract_email(raw: str | None) -> str:
    if not raw:
        return ""
    _, addr = parseaddr(raw)
    return (addr or raw).strip().lower()


def _header_map(payload: dict[str, Any]) -> dict[str, str]:
    headers = payload.get("headers") or []
    out: dict[str, str] = {}
    for h in headers:
        name = (h.get("name") or "").lower()
        if name:
            out[name] = h.get("value") or ""
    return out


async def _google_profile(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code >= 400:
            raise GmailAuthError("Gmail token rejected. Connect Gmail again.")
        return r.json()


async def _gmail_list_ids_for_query(
    access_token: str, q: str, *, max_results: int = 40
) -> list[str]:
    params = {"maxResults": max_results, "q": q}
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.get(
            f"{GMAIL_API}/users/me/messages",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code in {401, 403}:
            raise GmailAuthError()
        if r.status_code >= 400:
            raise GmailApiError(r.text[:200] or GmailApiError.message)
        data = r.json()
        return [m["id"] for m in (data.get("messages") or []) if m.get("id")]


def _crm_search_query(contacts: list[dict[str, Any]]) -> str | None:
    """Targeted Gmail search for known CRM accounts / contacts (recent sales mail)."""
    parts: list[str] = []
    seen: set[str] = set()
    # Prefer recovery / open pipeline heroes first
    prioritized = sorted(
        contacts,
        key=lambda c: (
            0 if c.get("account_id") in {"ACC-0178", "ACC-0180", "ACC-0189"} else 1,
            0 if c.get("deal_status") in {"lost", "inactive", "open", "stalled"} else 1,
        ),
    )
    for c in prioritized[:40]:
        for phrase in _account_search_phrases(c):
            key = phrase.lower()
            if key in seen or len(phrase) < 3:
                continue
            seen.add(key)
            # Quote multi-word phrases for Gmail
            if " " in phrase:
                parts.append(f'"{phrase}"')
            else:
                parts.append(phrase)
            if len(parts) >= 18:
                break
        if len(parts) >= 18:
            break
    if not parts:
        return None
    or_clause = " OR ".join(parts)
    return (
        f"(in:inbox OR in:sent) newer_than:30d "
        f"-category:promotions -category:social -category:forums "
        f"({or_clause})"
    )


async def _gmail_list_ids(
    access_token: str, contacts: list[dict[str, Any]]
) -> list[str]:
    """Merge recent mailbox + CRM-targeted search so the latest sales email is not missed."""
    broad = await _gmail_list_ids_for_query(
        access_token,
        "(in:inbox OR in:sent) newer_than:14d "
        "-category:promotions -category:social -category:forums",
        max_results=40,
    )
    targeted_q = _crm_search_query(contacts)
    targeted: list[str] = []
    if targeted_q:
        try:
            targeted = await _gmail_list_ids_for_query(
                access_token, targeted_q, max_results=40
            )
        except GmailApiError:
            targeted = []
    # Targeted first (more relevant), then broad; preserve order / uniqueness
    ordered: list[str] = []
    seen: set[str] = set()
    for mid in targeted + broad:
        if mid not in seen:
            seen.add(mid)
            ordered.append(mid)
    return ordered


async def _gmail_get_message(access_token: str, message_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{GMAIL_API}/users/me/messages/{message_id}",
            params={
                "format": "metadata",
                "metadataHeaders": ["From", "To", "Cc", "Subject", "Date"],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code in {401, 403}:
            raise GmailAuthError()
        if r.status_code >= 400:
            raise GmailApiError(r.text[:200] or GmailApiError.message)
        return r.json()


def _participants(headers: dict[str, str]) -> list[str]:
    emails: list[str] = []
    for key in ("from", "to", "cc"):
        raw = headers.get(key) or ""
        for part in raw.split(","):
            addr = _extract_email(part)
            if addr and addr not in emails:
                emails.append(addr)
    return emails


# Demo / common short names for hero accounts (helps subject lines like "ASU MyLab")
_ACCOUNT_ALIASES: dict[str, list[str]] = {
    "ACC-0178": ["asu", "arizona state", "arizona state university"],
    "ACC-0180": ["csu", "cal state", "california state", "california state university"],
    "ACC-0189": ["osu", "ohio state", "the ohio state university"],
}


def _name_tokens(account_name: str) -> list[str]:
    stop = {"the", "of", "and", "university", "college", "district", "inc", "ltd", "department"}
    tokens = re.findall(r"[a-z0-9]+", (account_name or "").lower())
    # Keep "state" when paired context exists via aliases; drop alone if short noise
    return [t for t in tokens if len(t) > 2 and t not in stop]


def _contact_name_parts(contact_name: str | None) -> list[str]:
    if not contact_name:
        return []
    parts = re.findall(r"[a-zA-Z]{3,}", contact_name)
    return [p.lower() for p in parts]


def _account_search_phrases(contact: dict[str, Any]) -> list[str]:
    phrases: list[str] = []
    aid = contact.get("account_id") or ""
    name = (contact.get("account_name") or "").strip()
    if name:
        phrases.append(name)
    for alias in _ACCOUNT_ALIASES.get(aid, []):
        phrases.append(alias)
    tokens = _name_tokens(name)
    # Distinctive single tokens (arizona, california, ohio, melbourne…)
    phrases.extend(t for t in tokens if len(t) >= 5)
    cname = (contact.get("contact_name") or "").strip()
    if cname:
        phrases.append(cname)
    return phrases


def _is_sales_related(subject: str, snippet: str, match_type: str) -> bool:
    """Any CRM match for this product is sales context; also accept sales keywords."""
    if match_type in {"contact_email", "contact_name", "account_name_hint", "account_alias"}:
        return True
    hay = f"{subject} {snippet}".lower()
    return any(term in hay for term in _SALES_TERMS)


async def _load_crm_contacts(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                """
                select account_id, account_name, contact_name, contact_email,
                       deal_status, deal_value, currency,
                       last_activity_date::text as last_activity_date,
                       last_contacted_date::text as last_contacted_date,
                       inactivity_days, recovery_eligibility,
                       as_of_date::text as as_of_date, activity_history
                from crm_master
                where contact_email is not null and contact_email <> ''
                """
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def _load_approved_message_ids(session: AsyncSession) -> set[str]:
    """Only explicit gmail_message_id values already written to CRM."""
    approved = set(_APPROVED_IDS)
    rows = (
        await session.execute(
            text(
                """
                select activity_history
                from crm_master
                where activity_history is not null
                """
            )
        )
    ).scalars().all()
    for raw in rows:
        for h in _parse_history(raw):
            mid = h.get("gmail_message_id")
            if isinstance(mid, str) and mid.strip():
                approved.add(mid.strip())
    return approved


def _already_logged(history: list[dict[str, Any]], gmail_message_id: str) -> bool:
    if gmail_message_id in _APPROVED_IDS:
        return True
    for h in history:
        if h.get("gmail_message_id") == gmail_message_id:
            return True
    return False


def _match_account(
    participants: list[str],
    subject: str,
    snippet: str,
    from_header: str,
    contacts: list[dict[str, Any]],
    mailbox_email: str,
) -> tuple[dict[str, Any] | None, str]:
    mailbox = (mailbox_email or "").lower()
    external = [e for e in participants if e and e != mailbox]
    by_email = {
        (c.get("contact_email") or "").strip().lower(): c
        for c in contacts
        if (c.get("contact_email") or "").strip()
    }
    for e in external:
        if e in by_email:
            return by_email[e], "contact_email"

    hay = f"{from_header} {subject} {snippet}".lower()

    # Explicit aliases (ASU / CSU / OSU, full names)
    for c in contacts:
        aid = c.get("account_id") or ""
        for alias in _ACCOUNT_ALIASES.get(aid, []):
            if alias in hay:
                return c, "account_alias"

    # Contact person name (e.g. Omar Fischer)
    best_contact: dict[str, Any] | None = None
    best_contact_hits = 0
    for c in contacts:
        parts = _contact_name_parts(c.get("contact_name"))
        if len(parts) < 1:
            continue
        hits = sum(1 for p in parts if p in hay)
        need = 2 if len(parts) >= 2 else 1
        if hits >= need and hits > best_contact_hits:
            best_contact = c
            best_contact_hits = hits
    if best_contact:
        return best_contact, "contact_name"

    # Account name tokens — one distinctive token (len>=4) is enough
    best: dict[str, Any] | None = None
    best_hits = 0
    best_score = 0
    for c in contacts:
        tokens = _name_tokens(c.get("account_name") or "")
        if not tokens:
            continue
        hits = sum(1 for t in tokens if t in hay)
        # Prefer longer token hits (arizona > metro)
        score = sum(len(t) for t in tokens if t in hay)
        if hits >= 1 and score >= 4 and (hits > best_hits or score > best_score):
            best = c
            best_hits = hits
            best_score = score
    if best:
        return best, "account_name_hint"
    return None, "none"


def _propose_patch(account: dict[str, Any], msg: dict[str, Any]) -> dict[str, Any]:
    as_of = account.get("as_of_date") or date.today().isoformat()
    status = account.get("deal_status") or "unknown"
    direction = msg.get("direction") or "inbound"
    interpretation = (
        "Inbound sales/lead email matched to an existing CRM account — may be worth reviewing."
        if direction == "inbound"
        else "Outbound sales email matched to an existing CRM account."
    )
    status_note = (
        f"Current deal_status stays `{status}` until a human Reopens or changes it explicitly."
    )
    field_updates: dict[str, Any] = {
        "last_contacted_date": as_of,
        "last_activity_date": as_of,
        "inactivity_days": 0,
    }
    if status in {"lost", "inactive"} and account.get("recovery_eligibility") in {
        None,
        "",
        "review",
    }:
        field_updates["recovery_eligibility"] = "eligible"
    return {
        "interpretation": interpretation,
        "status_note": status_note,
        "current": {
            "deal_status": status,
            "recovery_eligibility": account.get("recovery_eligibility"),
            "last_activity_date": account.get("last_activity_date"),
            "inactivity_days": account.get("inactivity_days"),
        },
        "field_updates": field_updates,
        "will_not_change": [
            "deal_status (no auto reopen / no won)",
            "deal_value",
            "signal_source_url",
            "revenue is not marked recovered",
            "email is not sent",
        ],
    }


async def refresh_inbox(session: AsyncSession, access_token: str) -> dict[str, Any]:
    if not (access_token or "").strip():
        raise GmailAuthError("Missing Gmail access token.")

    profile = await _google_profile(access_token)
    mailbox_email = (profile.get("email") or "").strip().lower()
    if not mailbox_email:
        raise GmailAuthError("Could not read mailbox email from Google profile.")

    contacts = await _load_crm_contacts(session)
    ids = await _gmail_list_ids(access_token, contacts)
    approved_ids = await _load_approved_message_ids(session)

    scanned = 0
    skipped_approved = 0
    skipped_non_sales = 0
    skipped_no_crm = 0
    items: list[dict[str, Any]] = []
    recent_subjects: list[str] = []

    for mid in ids:
        if mid in approved_ids:
            skipped_approved += 1
            continue

        raw = await _gmail_get_message(access_token, mid)
        scanned += 1
        headers = _header_map(raw.get("payload") or {})
        participants = _participants(headers)
        frm = _extract_email(headers.get("from"))
        from_header = headers.get("from") or frm
        to = headers.get("to") or ""
        subject = headers.get("subject") or "(no subject)"
        snippet = raw.get("snippet") or ""
        if len(recent_subjects) < 8:
            recent_subjects.append(subject[:80])
        thread_id = raw.get("threadId") or mid
        internal_ts = int(raw.get("internalDate") or 0)
        iso = (
            datetime.fromtimestamp(internal_ts / 1000, tz=timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
            if internal_ts
            else datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        direction = "inbound" if frm and frm != mailbox_email else "outbound"

        account, match_type = _match_account(
            participants, subject, snippet, from_header, contacts, mailbox_email
        )
        if not account:
            skipped_no_crm += 1
            continue
        if not _is_sales_related(subject, snippet, match_type):
            skipped_non_sales += 1
            continue

        history = _parse_history(account.get("activity_history"))
        if _already_logged(history, mid):
            skipped_approved += 1
            _APPROVED_IDS.add(mid)
            continue

        proposed = _propose_patch(account, {"direction": direction})
        items.append(
            {
                "gmail_message_id": mid,
                "thread_id": thread_id,
                "date": iso,
                "from": from_header,
                "to": to,
                "subject": subject,
                "snippet": snippet,
                "direction": direction,
                "participants": participants,
                "crm_match": {
                    "account_id": account["account_id"],
                    "account_name": account["account_name"],
                    "contact_name": account.get("contact_name"),
                    "contact_email": account.get("contact_email"),
                    "deal_status": account.get("deal_status"),
                    "match_type": match_type,
                },
                "already_in_crm": False,
                "proposed_crm_update": proposed,
            }
        )

    # Newest first
    items.sort(key=lambda i: i.get("date") or "", reverse=True)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _INBOX_CACHE["synced_at"] = now
    _INBOX_CACHE["mailbox_email"] = mailbox_email
    _INBOX_CACHE["items"] = items

    return {
        "mailbox_email": mailbox_email,
        "synced_at": now,
        "total_scanned": scanned,
        "total_listed": len(ids),
        "pending_approval_count": len(items),
        "skipped_approved": skipped_approved,
        "skipped_no_crm_match": skipped_no_crm,
        "skipped_non_sales": skipped_non_sales,
        "items": items,
        "recent_subjects_sampled": recent_subjects,
        "notice": (
            "Live Gmail only · sales/lead + CRM match · already-approved hidden. "
            f"Scanned {scanned}, pending {len(items)}, "
            f"skipped approved {skipped_approved}, no CRM {skipped_no_crm}."
        ),
        "data_label": "Fictional demo data",
    }


def get_cached_inbox() -> dict[str, Any]:
    items = [
        i
        for i in (_INBOX_CACHE.get("items") or [])
        if i.get("crm_match") and not i.get("already_in_crm")
    ]
    return {
        "mailbox_email": _INBOX_CACHE.get("mailbox_email"),
        "synced_at": _INBOX_CACHE.get("synced_at"),
        "items": items,
        "pending_approval_count": len(items),
        "notice": "Cached pending sales leads. Sync again to pull new Gmail messages.",
        "data_label": "Fictional demo data",
    }


def _cached_item(gmail_message_id: str) -> dict[str, Any] | None:
    for item in _INBOX_CACHE.get("items") or []:
        if item.get("gmail_message_id") == gmail_message_id:
            return item
    return None


async def preview_inbox_crm(
    session: AsyncSession, gmail_message_id: str
) -> dict[str, Any]:
    item = _cached_item(gmail_message_id)
    if not item:
        raise ValidationAppError("Message not in pending inbox. Sync Gmail again.")
    match = item.get("crm_match")
    if not match:
        raise ValidationAppError("No CRM account matched this email.")
    if item.get("already_in_crm") or gmail_message_id in _APPROVED_IDS:
        raise ValidationAppError("Already approved into CRM — removed from inbox queue.")

    row = (
        await session.execute(
            text(
                """
                select account_id, account_name, contact_email, deal_status,
                       recovery_eligibility, as_of_date::text as as_of_date,
                       activity_history
                from crm_master where account_id = :account_id
                """
            ),
            {"account_id": match["account_id"]},
        )
    ).mappings().first()
    if not row:
        raise ValidationAppError("Matched CRM account no longer exists.")

    if _already_logged(_parse_history(row.get("activity_history")), gmail_message_id):
        raise ValidationAppError("Already approved into CRM — removed from inbox queue.")

    proposed = item.get("proposed_crm_update") or _propose_patch(dict(row), item)
    return {
        "gmail_message_id": gmail_message_id,
        "account_id": row["account_id"],
        "account_name": row["account_name"],
        "requires_confirmation": True,
        "summary": (
            f"Apply sales email activity to {row['account_name']} "
            f"and refresh contact dates. Deal status stays {row['deal_status']}."
        ),
        "email": {
            "subject": item.get("subject"),
            "snippet": item.get("snippet"),
            "from": item.get("from"),
            "to": item.get("to"),
            "date": item.get("date"),
            "direction": item.get("direction"),
            "thread_id": item.get("thread_id"),
        },
        "match_type": match.get("match_type"),
        "interpretation": proposed.get("interpretation"),
        "status_note": proposed.get("status_note"),
        "current": proposed.get("current"),
        "proposed_activity": {
            "date": (item.get("date") or row.get("as_of_date") or date.today().isoformat())[:10],
            "type": "Email",
            "direction": item.get("direction") or "inbound",
            "description": f"{item.get('subject')}: {item.get('snippet')}",
            "outcome": "Logged from sales mailbox (human approved)",
            "classification": "SYNTHETIC",
            "gmail_message_id": gmail_message_id,
            "thread_id": item.get("thread_id"),
        },
        "field_updates": proposed.get("field_updates") or {},
        "will_not_change": proposed.get("will_not_change") or [],
        "data_label": "Fictional demo data",
    }


async def confirm_inbox_crm(
    session: AsyncSession, gmail_message_id: str, confirm: bool
) -> dict[str, Any]:
    if not confirm:
        raise ConfirmationRequiredError()
    preview = await preview_inbox_crm(session, gmail_message_id)
    account_id = preview["account_id"]
    row = (
        await session.execute(
            text(
                """
                select activity_history, recovery_eligibility
                from crm_master where account_id = :account_id
                """
            ),
            {"account_id": account_id},
        )
    ).mappings().one()
    history = _parse_history(row.get("activity_history"))
    history.append(preview["proposed_activity"])
    updates = preview["field_updates"]
    as_of = updates.get("last_contacted_date") or date.today().isoformat()
    eligibility = updates.get("recovery_eligibility", row.get("recovery_eligibility"))

    await session.execute(
        text(
            """
            update crm_master
            set activity_history = cast(:history as jsonb),
                last_contacted_date = cast(:as_of as date),
                last_activity_date = cast(:as_of as date),
                inactivity_days = 0,
                recovery_eligibility = coalesce(:eligibility, recovery_eligibility)
            where account_id = :account_id
            """
        ),
        {
            "history": json.dumps(history),
            "as_of": as_of,
            "eligibility": eligibility,
            "account_id": account_id,
        },
    )
    await session.commit()

    _APPROVED_IDS.add(gmail_message_id)
    # Remove from pending queue entirely
    _INBOX_CACHE["items"] = [
        i
        for i in (_INBOX_CACHE.get("items") or [])
        if i.get("gmail_message_id") != gmail_message_id
    ]

    return {
        "ok": True,
        "account_id": account_id,
        "gmail_message_id": gmail_message_id,
        "deal_status_unchanged": True,
        "notice": "CRM updated. This email is removed from the inbox queue.",
    }
