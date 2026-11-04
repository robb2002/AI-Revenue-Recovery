"""F1 §14 sample re-engagement drafts + §15 Gmail fixtures (demo mailbox)."""

from __future__ import annotations

from datetime import datetime, timezone

SAMPLES: dict[str, dict[str, str]] = {
    "ACC-0178": {
        "subject": "Reconnecting on MyLab / learning platform timing at ASU",
        "body": (
            "Hi {contact_name},\n\n"
            "I hope you are well. When we last spoke, the timing for moving forward on the "
            "learning platform evaluation was difficult ({lost_reason}).\n\n"
            "I noticed a recent public update related to AI and learning platforms at ASU and "
            "wanted to check whether it is a good moment to reconnect for a short working "
            "session—no proposal pressure.\n\n"
            "Would any time next week work for a 20-minute check-in?\n\n"
            "Best regards,\n{account_owner}\nLumora Learning"
        ),
    },
    "ACC-0180": {
        "subject": "Checking in — assessment / AI initiative timing",
        "body": (
            "Hi {contact_name},\n\n"
            "I am reaching out because our last conversation paused on timing and priorities "
            "({lost_reason}).\n\n"
            "Given recent public CSU/SDSU AI initiative updates on file, I wanted to see if a "
            "brief reconnect would help clarify whether Lumora’s assessment tools are still "
            "relevant for your team this term.\n\n"
            "Happy to work around your calendar.\n\n"
            "Regards,\n{account_owner}\nLumora Learning"
        ),
    },
    "ACC-0189": {
        "subject": "AI Fluency follow-up — worth a short reconnect?",
        "body": (
            "Hi {contact_name},\n\n"
            "You asked us to hold while internal priorities settled (inactivity on file). "
            "I saw the AI Fluency–related public update we have on record and thought a "
            "light-touch check-in might be useful.\n\n"
            "If helpful, I can send a one-page outline aligned to your last stated needs—"
            "still a draft for your review only.\n\n"
            "Thanks,\n{account_owner}\nLumora Learning"
        ),
    },
}

DEMO_MAILBOX = "rep@lumora-demo.example"


def render_sample(
    account_id: str, contact_name: str, account_owner: str, lost_reason: str
) -> dict[str, str] | None:
    raw = SAMPLES.get(account_id)
    if not raw:
        return None
    ctx = {
        "contact_name": contact_name or "there",
        "account_owner": account_owner or "Lumora Sales",
        "lost_reason": lost_reason or "timing and priorities",
    }
    return {
        "subject": raw["subject"],
        "body": raw["body"].format(**ctx),
    }


def _msg(
    *,
    mid: str,
    thread_id: str,
    date: str,
    frm: str,
    to: str,
    subject: str,
    snippet: str,
    classification: str,
    direction: str,
) -> dict:
    return {
        "gmail_message_id": mid,
        "thread_id": thread_id,
        "date": date,
        "from": frm,
        "to": to,
        "subject": subject,
        "snippet": snippet,
        "classification": classification,
        "direction": direction,
    }


def gmail_fixture(account_id: str, contact_email: str) -> dict:
    """University-specific demo thread: same contact_email + shared thread_id."""
    email = (contact_email or "").strip() or "contact@example.edu"
    rep = DEMO_MAILBOX
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    threads: dict[str, dict] = {
        "ACC-0178": {
            "key": "asu",
            "institution": "Arizona State University",
            "thread_id": "fixture_asu_thread_1",
            "new": _msg(
                mid="fixture_asu_new_001",
                thread_id="fixture_asu_thread_1",
                date="2026-10-28T15:12:00Z",
                frm=email,
                to=rep,
                subject="Re: Timing for MyLab evaluation",
                snippet=(
                    "Thanks for holding — can we revisit after our November planning meeting "
                    "at ASU? Same thread as our March exchange."
                ),
                classification="new",
                direction="inbound",
            ),
            "previous": [
                _msg(
                    mid="fixture_asu_prev_001",
                    thread_id="fixture_asu_thread_1",
                    date="2026-03-04T18:00:00Z",
                    frm=rep,
                    to=email,
                    subject="MyLab evaluation next steps",
                    snippet="Sharing the outline we discussed and proposed pilot scope for ASU.",
                    classification="previous",
                    direction="outbound",
                ),
                _msg(
                    mid="fixture_asu_prev_002",
                    thread_id="fixture_asu_thread_1",
                    date="2026-03-10T14:22:00Z",
                    frm=email,
                    to=rep,
                    subject="Re: MyLab evaluation next steps",
                    snippet="We need to pause — budget timing is the blocker for this quarter.",
                    classification="previous",
                    direction="inbound",
                ),
            ],
        },
        "ACC-0180": {
            "key": "csu",
            "institution": "California State University",
            "thread_id": "fixture_csu_thread_1",
            "new": _msg(
                mid="fixture_csu_new_001",
                thread_id="fixture_csu_thread_1",
                date="2026-10-22T16:40:00Z",
                frm=email,
                to=rep,
                subject="Re: Assessment timing",
                snippet=(
                    "Our AI learning workgroup reconvenes next month — happy to reopen the "
                    "assessment conversation then."
                ),
                classification="new",
                direction="inbound",
            ),
            "previous": [
                _msg(
                    mid="fixture_csu_prev_001",
                    thread_id="fixture_csu_thread_1",
                    date="2026-02-18T17:05:00Z",
                    frm=rep,
                    to=email,
                    subject="Assessment evaluation next steps",
                    snippet="Recap of discovery and suggested next evaluation workshop.",
                    classification="previous",
                    direction="outbound",
                ),
                _msg(
                    mid="fixture_csu_prev_002",
                    thread_id="fixture_csu_thread_1",
                    date="2026-02-25T13:11:00Z",
                    frm=email,
                    to=rep,
                    subject="Re: Assessment evaluation next steps",
                    snippet="Priorities shifted — please hold outreach until spring planning.",
                    classification="previous",
                    direction="inbound",
                ),
            ],
        },
        "ACC-0189": {
            "key": "osu",
            "institution": "The Ohio State University",
            "thread_id": "fixture_osu_thread_1",
            "new": _msg(
                mid="fixture_osu_new_001",
                thread_id="fixture_osu_thread_1",
                date="2026-10-30T19:05:00Z",
                frm=email,
                to=rep,
                subject="Re: AI Fluency check-in",
                snippet=(
                    "AI Fluency planning is moving again — can you send a short one-pager "
                    "aligned to our last requirements?"
                ),
                classification="new",
                direction="inbound",
            ),
            "previous": [
                _msg(
                    mid="fixture_osu_prev_001",
                    thread_id="fixture_osu_thread_1",
                    date="2026-04-02T15:30:00Z",
                    frm=rep,
                    to=email,
                    subject="AI Fluency follow-up",
                    snippet="Following up on the fluency pilot outline we walked through.",
                    classification="previous",
                    direction="outbound",
                ),
                _msg(
                    mid="fixture_osu_prev_002",
                    thread_id="fixture_osu_thread_1",
                    date="2026-04-09T12:48:00Z",
                    frm=email,
                    to=rep,
                    subject="Re: AI Fluency follow-up",
                    snippet="Please hold — internal priorities need to settle before we continue.",
                    classification="previous",
                    direction="inbound",
                ),
            ],
        },
    }

    spec = threads.get(account_id)
    if not spec:
        tid = f"fixture_gen_{account_id}_thread_1"
        new = _msg(
            mid=f"fixture_gen_{account_id}_new_001",
            thread_id=tid,
            date="2026-10-20T12:00:00Z",
            frm=email,
            to=rep,
            subject="Re: Follow-up",
            snippet="Can we revisit when priorities clear?",
            classification="new",
            direction="inbound",
        )
        previous = [
            _msg(
                mid=f"fixture_gen_{account_id}_prev_001",
                thread_id=tid,
                date="2026-03-01T12:00:00Z",
                frm=rep,
                to=email,
                subject="Earlier outreach",
                snippet="Checking in on the last evaluation conversation.",
                classification="previous",
                direction="outbound",
            ),
            _msg(
                mid=f"fixture_gen_{account_id}_prev_002",
                thread_id=tid,
                date="2026-03-08T12:00:00Z",
                frm=email,
                to=rep,
                subject="Re: Earlier outreach",
                snippet="Timing is difficult this quarter — please pause.",
                classification="previous",
                direction="inbound",
            ),
        ]
        institution = account_id
        thread_id = tid
    else:
        new = spec["new"]
        previous = list(spec["previous"])
        institution = str(spec["institution"])
        thread_id = str(spec["thread_id"])

    return {
        "account_id": account_id,
        "match_email": email,
        "mailbox_email": DEMO_MAILBOX,
        "mode": "demo_mailbox",
        "source": "demo_mailbox",
        "institution": institution,
        "thread_id": thread_id,
        "synced_at": now,
        "new_messages": [new],
        "previous_messages": previous,
        "message_count": 1 + len(previous),
        "notice": (
            "Read-only demo mailbox matched to this account's contact_email. "
            "Nothing was sent. Live Gmail OAuth uses the same DTO shape."
        ),
    }
