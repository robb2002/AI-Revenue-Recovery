# API Contract — AI Revenue Recovery & Deal Intelligence Agent

**Status:** APPROVED FOR MVP BUILD — aligned to `crm_master` (2026-11-04).  
**Supersedes:** multi-table `/companies`, `/deals/{deal_001}` import-centric draft.  
**Database:** `docs/DATABASE_DESIGN.md`. **Data:** `docs/DATA_SOURCES.md`.

## Purpose of this document

This is the interface between `frontend/` and `backend/`. Paths, fields, enums, and errors a screen
uses are defined here. If a screen needs something missing, update this document first.

---

## 1. Conventions

| Topic | Rule |
|---|---|
| Base path | `/api/v1` |
| Format | JSON, UTF-8, `snake_case` keys |
| Auth | `Authorization: Bearer <Clerk session token>` on every route except `GET /health` |
| Money | Number in USD (`deal_value`) |
| Dates | `YYYY-MM-DD`. Timestamps ISO 8601 UTC |
| Primary CRM key | `account_id` (e.g. `ACC-0181`). Opportunity: `opportunity_id` when present |
| As-of date | Time-based responses include `as_of_date` (`2026-11-04` for this dataset) |
| Demo label | Responses with CRM content include `"data_label": "Fictional demo data"` |
| Pagination | `limit` (default 25, max 100), `offset`. List: `{ items, total, limit, offset }` |
| Sorting | `sort` query where noted, e.g. `sort=-revenue_risk_score` |
| Long AI ops | Complete in one request (default timeout 60s) |
| Human approval | Approve/reject endpoints change draft/answer **state** only. Nothing is emailed or CRM-won by draft alone |

### 1.1 Error envelope

```json
{
  "error": {
    "code": "DEAL_NOT_WON",
    "message": "Handoff can be generated only for a won deal.",
    "details": {},
    "request_id": "req_…"
  }
}
```

### 1.2 Error codes

| HTTP | Code | When |
|---|---|---|
| 401 | `AUTH_MISSING` / `AUTH_INVALID` / `AUTH_EXPIRED` | Token problems |
| 404 | `NOT_FOUND` | Unknown `account_id` / meeting / draft id |
| 409 | `ACCOUNT_MATCH_AMBIGUOUS` | Upload match needs user confirmation |
| 409 | `DEAL_NOT_OPEN` | Action requires open/stalled opportunity |
| 409 | `DEAL_NOT_REOPENABLE` | Reopen only for lost/inactive (demo recovery pool) |
| 409 | `DEAL_NOT_WON` | Handoff requires won |
| 409 | `DEAL_ALREADY_WON` | Mark won on won row |
| 409 | `STATE_NOT_EDITABLE` | Draft/answer already approved or rejected |
| 413 | `TRANSCRIPT_TOO_LARGE` / `AUDIO_TOO_LARGE` / `FILE_TOO_LARGE` | Size limits |
| 415 | `UNSUPPORTED_MEDIA` | File type not allowed |
| 422 | `VALIDATION_ERROR` / `CONFIRMATION_REQUIRED` | Bad body / missing confirm |
| 429 | `STT_RATE_LIMITED` | Speech-to-text rate limit |
| 502 | `AI_UNAVAILABLE` / `AI_INVALID_OUTPUT` / `STT_UNAVAILABLE` | Provider failures |
| 504 | `AI_TIMEOUT` / `STT_TIMEOUT` | Timeouts |
| 500 | `INTERNAL_ERROR` | Unexpected |

`insufficient_evidence` is a **200** with `answer_status: "insufficient_evidence"`, not an error.

---

## 2. Shared objects

### 2.1 `Evidence`

```json
{
  "evidence_id": "string",
  "source_type": "crm_deal",
  "source_id": "ACC-0178",
  "source_title": "Lost reason",
  "source_date": "2026-04-18",
  "date_status": "available",
  "snippet": "Budget not approved in the prior planning cycle…",
  "relationship": "supports",
  "source_url": null,
  "data_origin": "synthetic"
}
```

`source_type` ∈ `crm_deal` | `activity` | `company_signal` | `transcript` | `kb_chunk`.  
For public signals / official KB excerpts, `source_url` may be set from **stored** values only.

### 2.2 `Claim`

```json
{ "claim_id": "c1", "layer": "fact", "text": "…", "evidence_ids": ["…"] }
```

`layer` ∈ `fact` | `interpretation` | `recommended_action`.

### 2.3 `AccountSummary`

```json
{
  "account_id": "ACC-0181",
  "account_name": "Georgia Institute of Technology",
  "opportunity_id": "OPP-0181",
  "opportunity_name": "MyLab for Georgia Institute of Technology (illustrative opportunity)",
  "deal_status": "open",
  "opportunity_stage": "Negotiation",
  "deal_value": 650000,
  "currency": "USD",
  "record_segment": "active_opportunity",
  "risk_category": "medium",
  "revenue_risk_score": 42,
  "inactivity_days": 8,
  "last_activity_date": "2026-09-25",
  "expected_close_date": "2026-12-15",
  "recovery_eligibility": null,
  "blocker_detected": true,
  "blocker_category": "Budget approval",
  "data_label": "Fictional demo data",
  "as_of_date": "2026-11-04"
}
```

### 2.4 `Draft`

```json
{
  "draft_type": "followup_email",
  "title": "Helping move the budget approval question forward",
  "subject": "…",
  "body": "…",
  "state": "draft",
  "requires_human_approval": true,
  "notice": "AI-generated draft. Approval does not send anything.",
  "account_id": "ACC-0181",
  "opportunity_id": "OPP-0181"
}
```

`draft_type` ∈ `reengagement_email` | `followup_email` | `proposal_outline` | `handoff`.  
`state` ∈ `draft` | `approved` | `rejected`.

---

## 3. Health and identity

### `GET /health` (public)

```json
{ "status": "ok", "database": "ok", "as_of_date": "2026-11-04", "crm_rows": 200, "version": "0.1.0" }
```

### `GET /me`

```json
{ "user_id": "uuid", "clerk_user_id": "user_…", "email": "rep@example.com", "role": "SALES_REP" }
```

---

## 4. Data status (no CSV import in MVP)

### `GET /data/status`

Replaces old `/import/*` for the preloaded database.

```json
{
  "has_data": true,
  "schema": "revenue_recovery",
  "table": "crm_master",
  "row_count": 200,
  "as_of_date": "2026-11-04",
  "knowledge_base_files_present": true,
  "uploaded_meetings_column": true,
  "data_label": "Fictional demo data"
}
```

`POST /import/sample` and `POST /import/reset` are **out of MVP** unless explicitly re-approved.

---

## 5. Accounts and dashboard

### `GET /accounts`

Query: `segment`, `deal_status`, `risk_category`, `recovery_eligibility`, `blocker_status`,
`q` (name search), `sort`, `limit`, `offset`.

Returns `{ items: AccountSummary[], total, limit, offset, as_of_date, data_label }`.

### `GET /accounts/{account_id}`

Full detail for one row: account, contact, opportunity, activity summary, `activity_history`,
meeting pre-generated fields, `uploaded_meetings`, signals, blocker, drafts, handoff fields,
`product_reference`, classifications. Always includes `data_label`.

### `GET /dashboard`

```json
{
  "as_of_date": "2026-11-04",
  "pipeline_open_usd": 0,
  "at_risk_usd": 0,
  "at_risk_note": "At-risk value is not lost revenue.",
  "recovery_eligible_count": 0,
  "high_risk_count": 0,
  "open_blocker_count": 0,
  "won_pending_handoff_count": 0,
  "briefing": [
    {
      "account_id": "ACC-…",
      "title": "…",
      "reason": "…",
      "recommended_action": "…",
      "priority": "high",
      "feature_key": "risk_prioritizer",
      "href": "/risk/ACC-…"
    }
  ],
  "data_label": "Fictional demo data"
}
```

Briefing items are rule-ordered. Risk-related items **must** include `account_id` and `href` to
`/risk/{account_id}` (F2 must-have deep link). Recovery items may use `/recovery/{account_id}`.
Do not combine at-risk USD with recovery USD into one “saved” number.

---

## 6. F1 — Lost lead recovery

### `GET /recovery`

Query: `eligibility=eligible|review`, `sort`, pagination.  
Items: AccountSummary + `lost_reason`, signal summary, draft subject preview.

### `GET /accounts/{account_id}/recovery`

Explanation payload: claims + evidence (lost reason, last activity, signal URL if
`PUBLIC_VERIFIED`), `recommended_next_action`, existing re-engagement draft fields.

### `POST /accounts/{account_id}/drafts/reengagement`

Generates or refreshes a re-engagement draft from stored fields. Body optional tone hints only —
no invented facts. Returns `Draft` with `state: draft`.

### `POST /accounts/{account_id}/reopen`

Body: `{ "confirm": true }`. Allowed when `deal_status` is `lost` or `inactive`. Sets status back
to an open working state per product rules; writes activity note. **Never** called automatically
after draft generation.

### Gmail (read) + CRM log (preview → human approve → CRM write)

Full brief: `docs/features/F1_LOST_LEAD_RECOVERY.md`. Gmail is **readonly** for MVP (no Send).

### `GET /gmail/connect` · `GET /gmail/callback` · `GET /gmail/status`

OAuth connect for the signed-in salesperson. Tokens stored outside `crm_master` (e.g.
`gmail_connections`). Status returns connected mailbox identity if any.

### `POST /accounts/{account_id}/gmail/sync`

Fetches Gmail messages matching the account’s `contact_email` (To/From/Cc). Returns
`new_messages` and `previous_messages` with `gmail_message_id`, dates, from/to, subject, snippet.
If Gmail is disconnected or fixtures mode is on, returns the PRD §15 fixture shape. Empty match
→ empty arrays (do not invent). No `contact_email` → `422 NO_CONTACT_EMAIL`. Does **not** write
CRM.

### `GET /accounts/{account_id}/gmail/thread`

Last synced thread DTO for the account (same shape as sync response).

### `GET /accounts/{account_id}/crm-log/preview`

No DB write. Body/query indicates `source=draft|gmail` and optional `gmail_message_id`.  
Returns proposed `activity_history` item, field updates, and `will_not_change` (deal_status stays
lost/inactive; not “recovered” revenue).

### `POST /accounts/{account_id}/crm-log/confirm`

Body: `{ "confirm": true, "source": "draft"|"gmail", "gmail_message_id"?, "subject"?, "body_summary"? }`.  
Applies preview in one transaction. Does **not** reopen or mark won. Without `confirm: true` →
`422 CONFIRMATION_REQUIRED`.

Aliases (same effect): `GET/POST .../email-sync/preview|confirm`,
`POST .../activities/email-sent`.

---

## 7. F2 — Revenue risk prioritizer

### `GET /risk`

Query: `band=high|medium|low`, `deal_status=open|stalled`,
`preset=needs_attention_today` (high band **or** overdue `next_followup_date` /
`next_action_date` vs row `as_of_date`), `sort=-revenue_risk_score`.  
Items include score, band, top reason line, value, inactivity, blocker flag, overdue flag.

Full brief: `docs/features/F2_REVENUE_RISK_PRIORITIZER.md`.

### `GET /accounts/{account_id}/risk`

```json
{
  "account_id": "ACC-0032",
  "revenue_risk_score": 88,
  "risk_category": "high",
  "risk_reason": "…",
  "factors": [
    { "key": "inactivity", "label": "Inactivity", "points": 25, "detail": "109 days since last activity" }
  ],
  "evidence": [ /* Evidence[] */ ],
  "recommended_next_action": "…",
  "as_of_date": "2026-11-04",
  "data_label": "Fictional demo data"
}
```

Scores are computed by rules (or read pre-seeded rule-consistent values). The model may explain; it
must not invent the number.

### `POST /accounts/{account_id}/risk/explain`

Optional. Returns layered claims + evidence from the stored score/factors only.

### `POST /accounts/{account_id}/risk/recompute`

**Must-have.** Rules only. Refreshes `revenue_risk_score` / `risk_category` / `risk_reason`.
Also invoked automatically after a successful risk-action confirm.

### Risk action log (preview → human approve → CRM write)

Mirrors F1 CRM-log pattern for logging the recommended next action (see
`docs/features/F2_REVENUE_RISK_PRIORITIZER.md`):

### `GET /accounts/{account_id}/risk-action/preview`

No DB write. Proposed `activity_history` item, `next_action` / follow-up date updates, and
`will_not_change` (includes deal_status unchanged; at-risk ≠ lost revenue).

### `POST /accounts/{account_id}/risk-action/confirm`

Body: `{ "confirm": true }`. Applies preview in one transaction, then **recomputes** risk score.
Does not mark lost/won.

---

## 8. F3 — Meeting intelligence

Allowed upload types: transcript `txt|docx|pdf`; audio `mp3|wav|m4a` (should-have STT).

### `POST /meetings/upload`

`multipart/form-data`: `file`, optional `account_id`, optional `opportunity_id`.  
Validates type/size; stores file in object storage; extracts text (STT if audio).  
Returns preview: transcript text, suggested account matches, confidence.

If multiple matches: `409 ACCOUNT_MATCH_AMBIGUOUS` with candidate list, or `200` with
`needs_confirmation: true`.

### `POST /meetings/extract`

Body: `{ "transcript": "…", "account_id": "ACC-0181", "opportunity_id": "OPP-0181" }`.  
Returns structured extraction (summary, requirements, budget, pain points, objections,
stakeholders, competitors, decision criteria, commitments, action items, deadlines, next steps)
with per-field status `confirmed|unconfirmed|unknown` where applicable. **Not persisted yet.**

### `POST /meetings/save/preview` (recommended)

No DB write. Returns the object that would be appended to `uploaded_meetings` and a
`will_not_change` list (pre-generated `meeting_*` kept; deal stage/status unchanged).

### `POST /meetings/save`

Body: `{ "confirm": true, "account_id": "…", "opportunity_id": "…", "storage_path": "…",
"transcript": "…", "extraction": { … } }`.  
Appends one object to `uploaded_meetings`. Does not overwrite pre-generated `meeting_*` columns.
Does not change `deal_status` / stage. Without `confirm: true` → `422 CONFIRMATION_REQUIRED`.

### `GET /accounts/{account_id}/meetings`

Returns pre-generated meeting fields plus `uploaded_meetings` array.

Demo file: `backend/data/crm_master/sample_meetings/ACC-0181_followup_call_2026-10-28.txt`.  
Full brief: `docs/features/F3_MEETING_INTELLIGENCE.md`.

---

## 9. F4 — Blocker resolution

### `GET /accounts/{account_id}/blocker`

Returns blocker fields + `supporting_document_reference`.

### `POST /accounts/{account_id}/blocker/answer`

Body: `{ "question": "Does MyLab sync grades to Canvas?" }`.  
Retrieves from embedded KB (and optional salesperson uploads). Returns:

```json
{
  "answer_status": "answered",
  "answer_text": "…",
  "citations": [
    { "doc_id": "KB-OFF-02", "title": "…", "snippet": "Syncing is one-way…", "source_url": "https://…" }
  ],
  "model_called": true,
  "notice": "Draft for human review. Not sent.",
  "state": "draft"
}
```

`answer_status` ∈ `answered` | `partially_answered` | `insufficient_evidence`.

### `POST /blocker-answers/{answer_id}/approve` / `…/reject`

Changes state only.

### `POST /knowledge/index`

Reindex bundled markdown under `backend/data/crm_master/knowledge_base/` into `kb_chunks`.

### `POST /knowledge/upload` (should-have)

Salesperson PDF/DOCX/TXT → storage → chunk/embed with `source=salesperson_upload`.

### `GET /knowledge/documents`

Lists KB doc ids/titles available for retrieval (from files or index metadata).

Full brief: `docs/features/F4_BLOCKER_RESOLUTION.md`. Planted questions and expected
`answer_status` values are defined there and in `knowledge_base/README.md`.

---

## 10. F5 — Follow-up and proposal

### `GET /accounts/{account_id}/drafts`

Returns follow-up and proposal draft fields / `proposal_draft` jsonb.

### `POST /accounts/{account_id}/drafts/followup`

Generate/refresh follow-up email draft from requirements + meeting context. `state: draft`.

### `POST /accounts/{account_id}/drafts/proposal`

Generate/refresh proposal outline. Must not invent prices or unlisted capabilities; use
`product_reference` / confirmed requirements.

### `PATCH /accounts/{account_id}/drafts/{draft_type}`

Body: `{ "subject"?, "body"?, "sections"? }` while `state = draft`.

### `POST /accounts/{account_id}/drafts/{draft_type}/approve`  
### `POST /accounts/{account_id}/drafts/{draft_type}/reject`

State change only. Approval does not send email and does not mark won.

Full brief: `docs/features/F5_FOLLOWUP_PROPOSAL.md`. Draft types for F5:
`followup_email`, `proposal_outline` (F1 owns `reengagement_email`). Completeness gaps and
no-invented-price rules are defined there.

---

## 11. F6 — Handoff

### `POST /accounts/{account_id}/mark-won`

Body: `{ "confirm": true }`. Only from an open (or agreed) working status. Sets `deal_status=won`,
`handoff_required=true`. Audit/activity note recommended.

### `GET /accounts/{account_id}/handoff`

Returns handoff pack fields for won rows.

### `POST /accounts/{account_id}/handoff/generate`

Builds/refreshes structured handoff from CRM + meetings + approved drafts. Returns draft handoff
for review. Errors `409 DEAL_NOT_WON` if not won.

### `POST /accounts/{account_id}/handoff/approve`

Marks handoff review state (`handoff_status`) per product rules.

Full brief: `docs/features/F6_CUSTOMER_HANDOFF.md`. Mark-won confirm UX, pack shape, and
`DEAL_NOT_WON` / `CONFIRM_REQUIRED` errors are defined there.

---

## 12. F7 — Signal Scout (stretch)

Full brief: `docs/features/F7_SIGNAL_SCOUT.md`. Pre-RFP public signals + potential opportunities.
Build only after F1–F6 must-haves unless explicitly prioritized.

| Method | Path | Notes |
|---|---|---|
| GET | `/signal-scout/targets/search` | CRM + recent manual targets |
| POST | `/signal-scout/targets` | From `account_id` or `{ name, website_url }` |
| GET | `/signal-scout/targets/{target_id}` | Card: name, URL, last scanned |
| POST | `/signal-scout/targets/{target_id}/scan` | `202` + `scan_id` |
| GET | `/signal-scout/scans/{scan_id}` | Poll status |
| GET | `/signal-scout/targets/{target_id}/signals` | Evidence-backed signals |
| GET | `/signal-scout/targets/{target_id}/opportunities` | Potential opportunities |
| GET | `/signal-scout/opportunities/{opportunity_id}` | Detail + score factors |
| POST | `/signal-scout/opportunities/{id}/explain` | AI explains rules score only |

---

## 13. Endpoint summary

| Method | Path | Feature |
|---|---|---|
| GET | `/health` | Ops |
| GET | `/me` | Auth |
| GET | `/data/status` | Data |
| GET | `/dashboard` | Shell |
| GET | `/accounts`, `/accounts/{account_id}` | CRM |
| GET | `/recovery`, `/accounts/{id}/recovery` | F1 |
| POST | `/accounts/{id}/drafts/reengagement`, `/reopen`, `/gmail/sync`, `/crm-log/*` | F1 |
| GET | `/gmail/connect`, `/gmail/callback`, `/gmail/status`, `/accounts/{id}/gmail/thread` | F1 |
| GET | `/risk`, `/accounts/{id}/risk` | F2 |
| POST | `/meetings/upload`, `/extract`, `/save` | F3 |
| GET | `/accounts/{id}/meetings` | F3 |
| GET | `/accounts/{id}/blocker` | F4 |
| POST | `/accounts/{id}/blocker/answer` | F4 |
| POST | `/blocker-answers/{id}/approve\|reject` | F4 |
| GET/POST | `/knowledge/*` | F4 |
| GET/POST/PATCH | `/accounts/{id}/drafts…` | F5 |
| POST | `/accounts/{id}/mark-won`, `/handoff/*` | F6 |
| GET/POST | `/signal-scout/*` | F7 stretch |

---

## Open questions

1. Exact max upload sizes for transcript/audio/PDF.  
2. Whether blocker answers are persisted on `crm_master` (new jsonb) or a tiny side table — prefer
   jsonb on the row or response-only for MVP speed; decide before Phase F4 persist.  
3. Clerk instance confirmation (`AUTHENTICATION.md`).  

---

## Document history

| Date | Change |
|---|---|
| 2026-11-04 | Rewrote contract for single-table `crm_master` and preloaded data |
