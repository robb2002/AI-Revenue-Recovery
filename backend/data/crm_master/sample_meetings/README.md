# Sample meetings for live upload (Meeting Intelligence)

Data only. No upload API, no speech-to-text, no embeddings yet.

## Target CRM row (clear match)

| Field | Value |
|---|---|
| account_id | `ACC-0181` |
| account_name | Georgia Institute of Technology |
| opportunity_id | `OPP-0181` |
| opportunity_name | MyLab for Georgia Institute of Technology (illustrative opportunity) |
| contact | Amara Bennett, Director of Digital Learning (SYNTHETIC) |
| account_owner | Sophie Laurent (SYNTHETIC) |
| deal_status | open |
| stage | Negotiation |
| open blocker | Budget approval |

The transcript below names this institution, opportunity and people on purpose so automatic matching can succeed during the event.

## Files

| File | Use |
|---|---|
| `ACC-0181_followup_call_2026-10-28.txt` | Primary demo upload (TXT) |
| `ACC-0181_followup_call_2026-10-28.wav` | Optional audio path (short read-aloud of the opening; SYNTHETIC speech) |
| `UNSUPPORTED_notes.csv` | Negative test: unsupported format |

## Database

`uploaded_meetings` on `crm_master` is an empty JSONB array (`[]`) on every row. Do **not** pre-fill it. A live upload during the event appends one object. Existing `meeting_*` columns on this account stay unchanged.

## Held-back fact (do not invent)

The transcript never states a signed contract value or a final discount. If extraction invents "USD 650,000 approved" or "15% discount agreed", that is a product defect. The only budget line in the transcript is that committee review is still pending.
