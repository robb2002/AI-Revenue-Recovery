"""Gmail readonly sync for F1 — match messages to account contact_email."""

from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.core.errors import AppError
from app.services.f1_samples import gmail_fixture

logger = logging.getLogger("app.gmail")

GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
MAX_RESULTS = 100
MAX_DETAIL = 100
MAX_LIST_PAGES = 5
MAX_BODY_CHARS = 8000

SALES_KEYWORDS = (
    "sales",
    "quote",
    "quotation",
    "proposal",
    "purchase",
    "purchasing",
    "pricing",
    "price",
    "deal",
    "opportunity",
    "contract",
    "rfp",
    "rfq",
    "demo",
    "demonstration",
    "lms",
    "learning",
    "subscription",
    "invoice",
    "procurement",
)


class NoContactEmailError(AppError):
    status_code = 422
    code = "NO_CONTACT_EMAIL"
    message = "This account has no contact_email to match in Gmail."


class GmailNotConnectedError(AppError):
    status_code = 422
    code = "GMAIL_NOT_CONNECTED"
    message = "Connect Gmail first, then Sync again."


class GmailUnavailableError(AppError):
    status_code = 502
    code = "GMAIL_UNAVAILABLE"
    message = "Gmail API request failed."


def _header(headers: list[dict[str, str]] | None, name: str) -> str:
    if not headers:
        return ""
    for item in headers:
        if str(item.get("name", "")).lower() == name.lower():
            return str(item.get("value") or "").strip()
    return ""


def _parse_date(message: dict[str, Any]) -> str:
    internal = message.get("internalDate")
    if internal:
        try:
            return datetime.fromtimestamp(int(internal) / 1000, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        except (TypeError, ValueError, OSError):
            pass
    date_header = _header(message.get("payload", {}).get("headers"), "Date")
    if date_header:
        try:
            return parsedate_to_datetime(date_header).astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        except (TypeError, ValueError, IndexError):
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _decode_b64url(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _walk_parts(payload: dict[str, Any] | None) -> tuple[str, str]:
    """Return (text_plain, text_html) from a Gmail payload tree."""
    if not payload:
        return "", ""
    mime = str(payload.get("mimeType") or "").lower()
    body_data = str(((payload.get("body") or {}).get("data")) or "")
    plain, html = "", ""
    if body_data:
        decoded = _decode_b64url(body_data)
        if mime == "text/plain":
            plain = decoded
        elif mime == "text/html":
            html = decoded
        elif mime.startswith("text/") and "html" in mime:
            html = decoded
        elif mime.startswith("text/"):
            plain = decoded
        elif not mime.startswith("multipart/") and decoded:
            # Single-part messages sometimes omit a clear mime type.
            if "<html" in decoded.lower() or "<div" in decoded.lower():
                html = decoded
            else:
                plain = decoded
    for part in payload.get("parts") or []:
        if not isinstance(part, dict):
            continue
        child_plain, child_html = _walk_parts(part)
        if child_plain and len(child_plain) > len(plain):
            plain = child_plain
        if child_html and len(child_html) > len(html):
            html = child_html
    return plain, html


def _html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)</div>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_body(message: dict[str, Any]) -> str:
    plain, html = _walk_parts(message.get("payload"))
    body = (plain or "").strip() or _html_to_text(html)
    if not body:
        body = str(message.get("snippet") or "").strip()
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS].rstrip() + "…"
    return body


def _looks_sales_related(subject: str, snippet: str, body: str = "") -> bool:
    haystack = f"{subject} {snippet} {body}".lower()
    return any(keyword in haystack for keyword in SALES_KEYWORDS)


def _map_message(message: dict[str, Any], classification: str) -> dict[str, Any]:
    headers = (message.get("payload") or {}).get("headers")
    snippet = str(message.get("snippet") or "").strip()
    body = _extract_body(message)
    return {
        "gmail_message_id": str(message.get("id") or ""),
        "thread_id": str(message.get("threadId") or ""),
        "date": _parse_date(message),
        "from": _header(headers, "From") or "Unknown",
        "to": _header(headers, "To") or "",
        "subject": _header(headers, "Subject") or "(No subject)",
        "snippet": snippet,
        "body": body or snippet,
        "classification": classification,
        "is_unread": "UNREAD" in (message.get("labelIds") or []),
    }


async def _gmail_get(url: str, access_token: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as exc:
        logger.warning("Gmail transport error (%s)", type(exc).__name__)
        raise GmailUnavailableError() from exc

    if response.status_code == 401:
        raise GmailNotConnectedError("Gmail token expired or invalid. Connect Gmail again.")
    if response.status_code == 403:
        raise GmailUnavailableError(
            "Gmail permission missing. Reconnect and allow gmail.readonly."
        )
    if response.status_code >= 400:
        logger.warning("Gmail API error status=%s", response.status_code)
        raise GmailUnavailableError()

    return response.json()


def _is_synthetic_contact(email: str) -> bool:
    domain = email.split("@")[-1].lower()
    return domain in {"example.com", "example.org", "example.net", "test.com"} or domain.endswith(
        ".example"
    )


async def _list_message_ids(access_token: str, query: str) -> list[str]:
    """Page through Gmail list results up to MAX_DETAIL ids."""
    ids: list[str] = []
    page_token: str | None = None
    for _ in range(MAX_LIST_PAGES):
        url = f"{GMAIL_BASE}/messages?q={quote(query)}&maxResults={MAX_RESULTS}"
        if page_token:
            url += f"&pageToken={quote(page_token)}"
        listing = await _gmail_get(url, access_token)
        for item in listing.get("messages") or []:
            mid = str(item.get("id") or "")
            if mid:
                ids.append(mid)
            if len(ids) >= MAX_DETAIL:
                return ids[:MAX_DETAIL]
        page_token = listing.get("nextPageToken")
        if not page_token:
            break
    return ids


async def _fetch_message_details(
    access_token: str, ids: list[str]
) -> list[dict[str, Any]]:
    """Fetch full message payloads so body text is available (not just snippet)."""
    messages: list[dict[str, Any]] = []
    for message_id in ids:
        detail = await _gmail_get(
            f"{GMAIL_BASE}/messages/{message_id}?format=full",
            access_token,
        )
        messages.append(detail)
    return messages


def _classify_messages(
    messages: list[dict[str, Any]],
    last_activity_date: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cutoff: datetime | None = None
    if last_activity_date:
        try:
            cutoff = datetime.fromisoformat(last_activity_date.replace("Z", "+00:00"))
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
        except ValueError:
            cutoff = None

    mapped: list[dict[str, Any]] = []
    for raw in messages:
        date_iso = _parse_date(raw)
        try:
            msg_dt = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
        except ValueError:
            msg_dt = datetime.now(timezone.utc)
        unread = "UNREAD" in (raw.get("labelIds") or [])
        if cutoff is not None:
            is_new = unread or msg_dt > cutoff
        else:
            is_new = unread
        mapped.append(_map_message(raw, "new" if is_new else "previous"))

    mapped.sort(key=lambda m: m["date"], reverse=True)
    new_messages = [m for m in mapped if m["classification"] == "new"]
    previous_messages = [m for m in mapped if m["classification"] == "previous"][:20]
    return new_messages, previous_messages


async def fetch_contact_thread(
    *,
    access_token: str,
    account_id: str,
    contact_email: str,
    last_activity_date: str | None,
) -> dict[str, Any]:
    email = contact_email.strip().lower()
    if not email or "@" not in email:
        raise NoContactEmailError()

    match_mode = "contact"
    notice = "Read-only Gmail sync. Nothing was sent or written to CRM."
    messages: list[dict[str, Any]] = []
    ids: list[str] = []

    # Demo CRM contacts use fictional emails (e.g. contact189@example.com). Skip the
    # useless contact query and load recent inbox mail for the hackathon demo.
    if not _is_synthetic_contact(email):
        query = f"(from:{email} OR to:{email} OR cc:{email})"
        ids = await _list_message_ids(access_token, query)
        messages = await _fetch_message_details(access_token, ids) if ids else []
        logger.info(
            "Gmail contact match account=%s email=%s hits=%s",
            account_id,
            email,
            len(ids),
        )

    if not messages:
        match_mode = "recent_inbox"
        recent_ids = await _list_message_ids(access_token, "in:inbox")
        if not recent_ids:
            recent_ids = await _list_message_ids(access_token, "newer_than:90d")
        recent_raw = await _fetch_message_details(access_token, recent_ids)
        sales_raw: list[dict[str, Any]] = []
        for raw in recent_raw:
            headers = (raw.get("payload") or {}).get("headers")
            subject = _header(headers, "Subject")
            snippet = str(raw.get("snippet") or "")
            body = _extract_body(raw)
            if _looks_sales_related(subject, snippet, body):
                sales_raw.append(raw)
        messages = sales_raw
        ids = [str(m.get("id") or "") for m in messages if m.get("id")]
        logger.info(
            "Gmail inbox fallback account=%s listed=%s sales=%s",
            account_id,
            len(recent_ids),
            len(messages),
        )
        if _is_synthetic_contact(email):
            notice = (
                f"CRM contact {email} is demo/synthetic, so Gmail cannot match it. "
                f"Showing {len(messages)} sales-related inbox message(s). Nothing was sent."
            )
        else:
            notice = (
                f"No Gmail threads matched CRM contact {email}. "
                f"Showing {len(messages)} sales-related inbox message(s). Nothing was sent."
            )

    new_messages, previous_messages = _classify_messages(messages, last_activity_date)
    # Recent-inbox fallback: show everything under New for the demo.
    if match_mode == "recent_inbox":
        combined = new_messages + previous_messages
        new_messages = combined
        previous_messages = []

    profile_email = ""
    try:
        profile = await _gmail_get(f"{GMAIL_BASE}/profile", access_token)
        profile_email = str(profile.get("emailAddress") or "")
    except AppError:
        profile_email = ""

    return {
        "account_id": account_id,
        "match_email": email,
        "match_mode": match_mode,
        "source": "gmail",
        "mailbox": profile_email,
        "scanned_count": len(ids),
        "new_messages": new_messages,
        "previous_messages": previous_messages,
        "notice": notice,
        "data_label": "Fictional demo data",
    }


def fixture_or_live_fallback(account_id: str, contact_email: str | None) -> dict[str, Any]:
    return gmail_fixture(account_id, contact_email or "")
