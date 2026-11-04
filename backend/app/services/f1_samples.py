"""F1 §14 sample re-engagement drafts + §15 Gmail fixtures."""

from __future__ import annotations

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


def render_sample(account_id: str, contact_name: str, account_owner: str, lost_reason: str) -> dict[str, str] | None:
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


def gmail_fixture(account_id: str, contact_email: str) -> dict:
    email = contact_email or "contact@example.edu"
    rep = "rep@lumora-demo.example"
    templates = {
        "ACC-0178": ("asu", "Re: Timing for MyLab evaluation", "MyLab evaluation next steps"),
        "ACC-0180": ("csu", "Re: Assessment timing", "Assessment evaluation next steps"),
        "ACC-0189": ("osu", "Re: AI Fluency check-in", "AI Fluency follow-up"),
    }
    key, new_subj, prev_subj = templates.get(account_id, ("gen", "Re: Follow-up", "Earlier outreach"))
    return {
        "account_id": account_id,
        "match_email": email,
        "source": "fixture",
        "new_messages": [
            {
                "gmail_message_id": f"fixture_{key}_new_001",
                "thread_id": f"fixture_{key}_thread_1",
                "date": "2026-10-28T15:12:00Z",
                "from": email,
                "to": rep,
                "subject": new_subj,
                "snippet": "Thanks for holding — can we revisit after our November planning meeting?",
                "body": (
                    "Thanks for holding — can we revisit after our November planning meeting?\n\n"
                    "Happy to pick up the evaluation once timing is clearer."
                ),
                "classification": "new",
            }
        ],
        "previous_messages": [
            {
                "gmail_message_id": f"fixture_{key}_prev_001",
                "thread_id": f"fixture_{key}_thread_1",
                "date": "2026-03-04T18:00:00Z",
                "from": rep,
                "to": email,
                "subject": prev_subj,
                "snippet": "Sharing the outline we discussed and proposed pilot scope.",
                "body": (
                    "Sharing the outline we discussed and proposed pilot scope.\n\n"
                    "Let me know if you want a follow-up call next week."
                ),
                "classification": "previous",
            },
            {
                "gmail_message_id": f"fixture_{key}_prev_002",
                "thread_id": f"fixture_{key}_thread_1",
                "date": "2026-03-10T14:22:00Z",
                "from": email,
                "to": rep,
                "subject": f"Re: {prev_subj}",
                "snippet": "We need to pause — budget timing is the blocker for this quarter.",
                "body": (
                    "We need to pause — budget timing is the blocker for this quarter.\n\n"
                    "Please keep the materials handy for when we reopen."
                ),
                "classification": "previous",
            },
        ],
    }
