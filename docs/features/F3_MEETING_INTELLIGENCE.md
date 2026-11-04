# Feature 3 PRD — Meeting Intelligence Extractor

**Status:** READY FOR EVENT IMPLEMENTATION  
**Feature key:** `meeting_intelligence`  
**Owner folders:** FE `frontend/src/pages/f3_meetings/` (+ optional `features/f3_meetings/`);  
BE `backend/app/api/routes/f3_meetings.py`, `backend/app/services/f3_meetings.py`,  
`backend/app/services/f3_stt.py` (should-have)  
**Branch:** `feat/f3-meetings`

---

## 0. How to use this PRD

1. Read `docs/features/README.md` (parallel module rules — **mandatory**).  
2. UI tokens/components: `docs/UI_UX_DESIGN.md` only (Premium Hybrid — same as F1/F2).  
3. APIs: `docs/API_CONTRACT.md` §8 (meetings).  
4. Data: `docs/DATABASE_DESIGN.md` §5.2–5.3 (`meeting_*`, `uploaded_meetings`).  
5. Demo files: `backend/data/crm_master/sample_meetings/` + `docs/DATA_SOURCES.md` §8.  
6. Grounding: `docs/AI_RAG_DESIGN.md` (extraction + quote checks).  
7. Do **not** generate automated test files unless asked.

F3 must not implement F1 email-sync, F2 risk scoring, F4 KB retrieval, F5 proposals, or F6 handoff
inside its modules (deep-links to other routes are OK).

---

## 1. Goal (judge-facing)

Let a salesperson **upload a meeting transcript (or audio)**, **extract structured customer
context**, **confirm the account**, and **save to CRM only after approval** — appending to
`uploaded_meetings` without wiping the prior meeting on the row.

**One-line pitch:** “Nothing important from the call is lost — and nothing is written to CRM
until you say so.”

---

## 2. Parallel development contract (F3-specific)

| Area | F3 owns | Must not modify |
|---|---|---|
| Routes UI | `/accounts/:accountId/meetings`, optional `/meetings/upload` wizard | F1/F2/F4–F6 pages; shell except nav |
| API | `/meetings/upload`, `/extract`, `/save`, `GET .../meetings` | Other feature routers |
| Services | File validate, storage path, STT adapter, extraction, match, append JSONB | Risk score, KB embed index (F4 owns index; F3 may read account fields only) |
| Shared | `crm_master` repo helpers; object storage client | Do not create a `meetings` CRM table |

**Commit hygiene:** F3 folders only (+ shared storage util if Platform-owned).

---

## 3. User stories

1. As a rep, I upload TXT/DOCX/PDF (or paste text) linked to an account.  
2. As a rep, I optionally upload short audio and get editable transcript text (should-have).  
3. As a rep, I see AI extraction with **confirmed / unconfirmed / unknown** per field.  
4. As a rep, I confirm account/opportunity when match is uncertain.  
5. As a rep, I preview what will be saved, then **approve Save to CRM**.  
6. As a rep, I still see the **pre-generated** meeting on the account after upload.  
7. As a rep, the system never invents an approved budget or discount when the transcript does not
   say so (held-back fact on ACC-0181).

---

## 4. Scope

### 4.1 In scope (MVP must)

- Upload validation: `txt`, `docx`, `pdf` (and reject others, e.g. sample CSV).  
- Store file in object storage; keep path in meeting JSON — **not** file bytes in JSONB.  
- Extract structured fields (see §5.4).  
- Account match: prefer explicit `account_id`; else name/id hints in transcript; confirm UI.  
- Extraction review table (editable values, remove row, status pills).  
- **Save preview → confirm → append** `uploaded_meetings`.  
- GET meetings: show `meeting_*` (legacy/pre-gen) **and** `uploaded_meetings[]` separately.  
- Duplicate upload handling: same content hash → warn; allow save as new meeting_id or skip.  
- Character limit (e.g. 100,000) → `413 TRANSCRIPT_TOO_LARGE`.  
- Demo path with `ACC-0181` sample TXT.  
- Premium Hybrid UI; indigo = Extract/AI only.

### 4.2 Out of scope

- Overwriting `meeting_transcript` / pre-gen columns on save.  
- Auto-changing `deal_status` / stage / won.  
- F4 answering from extraction without navigating to blockers.  
- Full mailbox sync.  
- Automated tests.  
- Scanning OCR-only image PDFs (nice-to-have cut).

### 4.3 Should-have

- STT: `mp3`/`wav`/`m4a` via Groq Whisper; editable text + “machine-transcribed” notice.  
- Optional merge of approved extraction into top-level `customer_requirements` (separate confirm).  
- Paste-only path without file.

---

## 5. Data

### 5.1 Demo target

| Field | Value |
|---|---|
| `account_id` | `ACC-0181` |
| Account | Georgia Institute of Technology |
| `opportunity_id` | `OPP-0181` |
| Contact | Amara Bennett |
| Sample TXT | `sample_meetings/ACC-0181_followup_call_2026-10-28.txt` |
| Sample WAV | same stem `.wav` |
| Reject sample | `UNSUPPORTED_notes.csv` |

**Held-back:** no approved budget amount, no discount %. Extraction must mark budget as pending
committee / `unconfirmed` or `unknown` — never invent `$650,000 approved`.

### 5.2 Read columns

`account_id`, `account_name`, `opportunity_id`, `opportunity_name`, `deal_status`, `contact_name`,
`meeting_date`, `meeting_type`, `meeting_summary`, `meeting_transcript`, `customer_requirements`,
`pain_points`, `budget_discussion`, `customer_objections`, `stakeholders`, `competitor_mentions`,
`decision_criteria`, `extracted_action_items`, `customer_commitments`, `meeting_insights`,
`uploaded_meetings`, `as_of_date`.

### 5.3 Write columns (after confirm only)

| Action | Write |
|---|---|
| Save meeting | **Append** one object to `uploaded_meetings`; bump `record_updated_at` |
| Optional activity | Append `activity_history` Meeting note (recommended) |
| Optional merge (should-have, separate confirm) | Patch `customer_requirements` / objections etc. — never silent |

### 5.4 Extraction schema (API + UI)

Each item should carry `value`, `status` (`confirmed`|`unconfirmed`|`unknown`), `quote` (verbatim
substring of transcript), optional `category`.

| Group | Examples |
|---|---|
| `meeting_summary` | Short paragraph |
| `customer_requirements` | Canvas SSO, grade passback, MyLab, Pearson+ |
| `budget_discussion` | Committee 2026-11-20; not approved |
| `pain_points` | Disconnected tools; material cost |
| `objections` | No budget vote before date |
| `stakeholders` | Amara / Tariq / Ravi + roles |
| `competitor_mentions` | “another adaptive practice platform” (unconfirmed name OK as unknown) |
| `decision_criteria` | Canvas, accessibility docs, access cost, plan |
| `customer_commitments` | Introduce committee chair; Canvas admin by Friday |
| `action_items` | Seller send LMS/grade-sync excerpts |
| `deadlines` | Written answers by 2026-11-12; committee 2026-11-20 |
| `recommended_next_steps` | Tech call week of 2026-11-04 |

### 5.5 `uploaded_meetings[]` object (required keys)

See `DATABASE_DESIGN.md` §5.3. Must include: `meeting_id`, `account_id`, `opportunity_id`,
`uploaded_file_name`, `uploaded_file_type`, `storage_path`, `upload_date`, `transcript`,
extraction fields, `processing_status` (`saved`), `data_classification` (`SYNTHETIC`),
optional `content_hash`.

---

## 6. Backend design

### 6.1 Modules

```
api/routes/f3_meetings.py
services/f3_meetings.py      # upload, match, extract, preview, save
services/f3_stt.py           # should-have Whisper adapter
```

### 6.2 Pipeline

```
validate file → store bytes in Storage → text (parse or STT)
 → suggest account matches → extract (model + quote validate)
 → return draft extraction (no CRM write)
 → save preview (optional) → confirm save → jsonb_set append uploaded_meetings
```

### 6.3 API

| Method | Path | Persist? |
|---|---|---|
| POST | `/api/v1/meetings/upload` | File to storage only |
| POST | `/api/v1/meetings/transcribe` | No (should-have) |
| POST | `/api/v1/meetings/extract` | No |
| GET | `/api/v1/meetings/save/preview` or POST body preview | No |
| POST | `/api/v1/meetings/save` `{confirm:true}` | Yes append |
| GET | `/api/v1/accounts/{account_id}/meetings` | Read |

Errors: `415 UNSUPPORTED_MEDIA`, `413`, `409 ACCOUNT_MATCH_AMBIGUOUS`, `422` without confirm,
`502` AI/STT failures (paste path remains).

### 6.4 Matching rules

1. If client sends `account_id` and it exists → use it (confidence high).  
2. Else scan transcript for `ACC-####` / `OPP-####` / exact `account_name`.  
3. If 0 matches → user must pick from search.  
4. If >1 → return candidates; UI confirm required.  
5. Never invent an account.

### 6.5 Extraction validation (defect prevention)

- Drop items without verbatim `quote` in transcript (after whitespace normalize).  
- Numeric guard: amounts/dates in claims must appear in transcript.  
- Held-back: if no approved budget language → status `unknown`/`unconfirmed`, no fabricated $.  
- Prompt-injection lines in transcript must not override system rules.  
- One retry on malformed JSON; then `502 AI_INVALID_OUTPUT`.

### 6.6 Save transaction

```sql
-- conceptual: read uploaded_meetings, append element, update row
-- WHERE account_id = $1
-- DO NOT SET meeting_transcript = ...
```

Also append activity: “Meeting upload saved (meeting_id=…)”.

---

## 7. Frontend design

### 7.1 Routes

- `/accounts/:accountId/meetings` — primary  
- Optional global “Upload meeting” entry that asks for account first  

Nav: **Meetings** / under account — icon `FileText` / `Mic`.

### 7.2 Visual system

Same Premium Hybrid as F1/F2:

| Element | Token |
|---|---|
| Extract button | `indigo-600` AI |
| Save to CRM | `navy-600` primary |
| confirmed | green outline pill |
| unconfirmed | amber outline pill |
| unknown | neutral pill |
| AI extraction panel | `surface-ai-subtle` |
| Success | green toast |

### 7.3 Screen flow (judge-ready)

1. **Existing meetings panel** — Pre-generated summary/transcript (collapsed). Uploaded list.  
2. **Upload zone** — FileDropzone; formats listed; CSV demo rejected with clear message.  
3. **Transcript editor** — editable; char count.  
4. **Match card** — account/opportunity; Confirm match.  
5. **Extract** — loading; then `ExtractionTable` grouped.  
6. **Save preview modal** — will append uploaded_meetings; will **not** overwrite prior meeting;
   will **not** change deal stage/status.  
7. **Confirm** — refetch; new card appears under Uploaded meetings.

### 7.4 States

Loading, empty (no uploads yet), error, AI unavailable (keep transcript), STT failure (keep paste),
ambiguous match, unsupported media, too large.

---

## 8. Scenarios (must pass)

1. Upload ACC-0181 TXT → auto-match → extract → confirm save → array length +1; `meeting_transcript` unchanged.  
2. Held-back: no invented approved budget/discount in extraction.  
3. Unsupported CSV → 415 / UI error; no storage object required.  
4. Save without confirm → no DB change.  
5. Ambiguous match → user must confirm.  
6. AI down → transcript still editable; extract shows unavailable.  
7. (should-have) WAV → editable transcript labeled machine-transcribed.  
8. Second upload → second array element; first preserved.

---

## 9. Guardrails

- Human confirm before CRM append.  
- Append-only `uploaded_meetings`.  
- No stage/won changes.  
- No invented facts.  
- Fictional demo label.  
- Files in Storage, not JSONB.  
- Single `crm_master` table.

---

## 10. Acceptance criteria (manual)

1. Demo TXT path works end-to-end on ACC-0181.  
2. Pre-gen and uploaded meetings both visible and distinct.  
3. Extraction statuses and quotes validated.  
4. Preview/cancel/confirm behavior correct.  
5. UI uses shared theme; indigo only for AI extract.  
6. Code isolated to F3 modules.  
7. Copy never claims deal won from meeting save.

---

## 11. Demo script (~2 min)

1. Open Georgia Tech account meetings. Show existing review call.  
2. Upload sample TXT → match ACC-0181.  
3. Extract → point at Canvas/grade sync + budget **not** approved.  
4. Save preview → Confirm → new uploaded meeting card.  
5. Bridge: “Those integration questions are answered in Feature 4 with citations.”

---

## 12. Dependencies

| Need | From |
|---|---|
| Auth, shell, storage config | Platform |
| Account page shell | Shared |
| F4 citations | Separate feature; deep-link only |

---

## 13. Open questions

1. Max file sizes (recommend: text 1 MB / audio 10 MB until Groq limits confirmed).  
2. DOCX/PDF parser library choice at event.  
3. Whether optional merge into top-level requirements is in MVP or cut.

---

## Document history

| Date | Change |
|---|---|
| 2026-11-04 | Initial F3 feature PRD (F1/F2 structure) |
