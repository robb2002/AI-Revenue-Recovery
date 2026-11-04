# Database Design — AI Revenue Recovery & Deal Intelligence Agent

**Status:** APPROVED FOR MVP BUILD — aligned to the live Supabase schema (2026-11-04).  
**Supersedes:** the earlier multi-table draft (`companies`, `deals`, `meetings`, `kb_documents`, …).  
**Authoritative DDL:** `backend/data/crm_master/schema.sql` (must match this document).

## Purpose of this document

This document defines the database objects the MVP uses: schema, the single CRM table, JSONB
shapes, indexes, classification rules, write rules for live features, and what must **not** be
created. It respects `AGENTS.md` and `docs/PRODUCT_PRD.md`. Endpoint shapes live in
`docs/API_CONTRACT.md` (still to be updated to this design). Sample-file import volumes in
`docs/DATA_SOURCES.md` are superseded by the loaded dataset unless that document is revised.

---

## 1. Principles

1. **Isolated schema.** Application objects live in PostgreSQL schema `revenue_recovery` inside the
   shared Supabase project. Do not create, alter, drop, or read CRM data in `public` or any other
   schema.
2. **One CRM table.** All account, contact, lead, opportunity, activity, meeting, signal, blocker,
   draft, and handoff fields for the demo sit on **`revenue_recovery.crm_master`**. Do not add
   parallel CRM tables (`companies`, `deals`, `meetings`, …) for this MVP.
3. **One row ≈ one account / opportunity context.** Primary business key for lists and APIs is
   `account_id` (text, unique). `id` is a UUID primary key. Opportunity context uses
   `opportunity_id` when present.
4. **Rules compute scores; models explain.** `revenue_risk_score`, bands, and similar numeric
   scores are produced by deterministic code (or were pre-seeded by the same rules). The LLM does
   not invent scores.
5. **Evidence stays on the row or in cited documents.** For the MVP, evidence is carried as stored
   field values, verbatim transcript snippets, `product_reference` / signal URLs, and knowledge-base
   file citations — not a separate `evidence` table.
6. **Human approval before CRM mutation from AI.** Drafts and extractions do not change
   `deal_status` to won/recovered by themselves. Live uploads **append** to `uploaded_meetings`
   only after salesperson confirmation/approval.
7. **Fixed demo clock.** Inactivity and overdue calculations use `as_of_date` (dataset value
   `2026-11-04`), not the wall clock.
8. **Closed vocabularies** for bands and segments use CHECKs below. Broader enums used in the
   product vocabulary (`AGENTS.md` §7) should be respected in application code even where the
   live table uses a slightly wider demo set (see §6).

---

## 2. Schema, extension, and connection

| Item | Value |
|---|---|
| Schema | `revenue_recovery` |
| CRM table | `revenue_recovery.crm_master` |
| Extension | `vector` enabled on the project (for future KB embeddings). **Not used by `crm_master` columns today.** |
| Connection | Supabase Session pooler Postgres URL in server `.env` only. Never expose DB credentials to React |
| Search path | Prefer `revenue_recovery` for app queries |

**Current load (do not re-seed unless asked):** 200 rows already present. Seeding scripts were
removed from the repo after load.

---

## 3. Entity overview (MVP)

```
revenue_recovery.crm_master     ← single CRM / opportunity row (200 loaded)

On disk (not DB rows yet):
  backend/data/crm_master/knowledge_base/*.md     ← F4 sources (embed at event)
  backend/data/crm_master/sample_meetings/*       ← F3 upload demo files

Optional at event (not CRM, only if needed):
  revenue_recovery.app_users                      ← Clerk identity cache (see AUTHENTICATION.md)
  revenue_recovery.kb_chunks (or equivalent)      ← embeddings for KB / uploads only
```

No `companies` / `contacts` / `deals` / `meetings` / `drafts` / `scores` / `evidence` tables in the
MVP database design.

---

## 4. Table: `revenue_recovery.crm_master`

### 4.1 Identity and keys

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `account_id` | text | Unique business key (`ACC-####`) |
| `account_name` | text | Institution / account name |
| `as_of_date` | date | Fixed demo date for day math |
| `record_segment` | text | See CHECK in §6 |
| `record_created_at` / `record_updated_at` | timestamptz | Defaults `now()` |

### 4.2 Column groups (feature map)

| Group | Columns (summary) | Primary features |
|---|---|---|
| A. Account | `account_type`, `institution_category`, `industry`, `country`, `state`, `city`, `website`, `organization_description`, population/employee estimates, `account_priority`, `account_status`, `account_owner`, `data_classification` | All |
| B. Contact | `contact_id`, `contact_name`, `contact_designation`, `contact_department`, `contact_role`, `is_decision_maker`, `contact_email`, `contact_phone` (always null), `contact_status` | F1–F6 |
| C. Lead / recovery | `lead_*`, `lost_reason`, `recovery_eligibility`, inactivity / follow-up dates | **F1** |
| D. Opportunity / risk | `opportunity_*`, `deal_value`, `deal_status`, `win_probability`, `weighted_pipeline_value`, close dates, competitor fields, `revenue_risk_score`, `opportunity_score`, `risk_category`, `risk_reason`, `recommended_next_action` | **F2**, F1 |
| E. Activity | `activity_*`, `previous_interaction_summary`, `sales_engagement_count`, `activity_history` (jsonb) | F1, F2 |
| F. Meeting | Pre-generated: `meeting_*`, extraction jsonb fields, `meeting_insights`. Live: `uploaded_meetings` (jsonb array) | **F3** |
| G. Signals | `signal_*`, `signal_classification`, `signal_source_url`, scores, recommended sales action | F1 |
| H. Blocker | `blocker_*`, `required_documentation`, `supporting_document_reference`, `suggested_resolution` | **F4** |
| I. Drafts | `proposal_*`, `proposal_draft`, `followup_email_*`, `followup_message_status`, `next_followup_recommendation` | **F5** |
| J. Handoff | `handoff_*`, `implementation_*`, `delivery_commitments`, `onboarding_checklist`, `sales_handoff_summary`, … | **F6** |
| K. Metadata | public source fields, `record_data_classification`, `field_classification`, `product_reference`, `institution_verification` | Guardrails |

Full column list and SQL types: `backend/data/crm_master/schema.sql`.

### 4.3 Important scalar enums (live table)

| Column | Allowed / used values |
|---|---|
| `deal_status` | `open` \| `won` \| `lost` \| `stalled` \| `inactive` \| `none` |
| `recovery_eligibility` | `eligible` \| `not_eligible` \| `review` \| null |
| `risk_category` / `account_priority` / `blocker_severity` | `high` \| `medium` \| `low` (nullable where noted) |
| `blocker_status` | includes `open`, `in_progress`, `resolved`, and demo values such as `closed_with_opportunity` |
| `proposal_status` / `followup_message_status` | `draft` \| `approved` \| `rejected` \| `none` |
| `signal_classification` | `PUBLIC_VERIFIED` \| `SYNTHETIC` |
| `data_classification` / `record_data_classification` | `PUBLIC_VERIFIED` \| `SYNTHETIC` \| `AI_GENERATED` |

**Note vs `AGENTS.md` §7:** product vocabulary prefers deal status `open|won|lost|postponed`. The
loaded demo also uses `stalled`, `inactive`, and `none`. Treat those as MVP demo statuses; do not
rename columns mid-event. Map UI labels carefully (“postponed/inactive” → recovery pool).

### 4.4 Classification rules

- Institution **identity / website** and **PUBLIC_VERIFIED signals** carry real official URLs only
  when `signal_classification = 'PUBLIC_VERIFIED'` (enforced: URL required).
- Contacts, deals, activities, meetings, blockers, and commercial values are **illustrative**
  (`SYNTHETIC`) unless a field group says otherwise in `field_classification`.
- Scores, explanations, draft bodies, and meeting insights are **AI_GENERATED** (scripted or model)
  and require human approval before external use.
- Every UI that shows demo CRM data must keep the **“Fictional demo data”** label. Real institution
  names used as targets must not be presented as real customers.

---

## 5. JSONB shapes

Application code must **append** or patch carefully. Never replace an entire array with a scalar.

### 5.1 `activity_history` (array)

Typical element:

```json
{
  "date": "2026-05-01",
  "type": "Email",
  "direction": "outbound",
  "description": "…",
  "outcome": "…",
  "classification": "SYNTHETIC"
}
```

### 5.2 Meeting extraction fields (pre-generated)

Used by F3 read path before any upload:

- `customer_requirements` — array of `{ requirement, priority, status, source }`
- `pain_points` — array of `{ pain_point, impact }`
- `customer_objections` — array of `{ objection, category, status }`
- `stakeholders` — array of `{ name, title, role, influence, sentiment, classification }`
- `competitor_mentions`, `decision_criteria`, `extracted_action_items`, `customer_commitments`
- `meeting_insights` — object with `classification`, summary fields

### 5.3 `uploaded_meetings` (array, live F3 only)

- Default: `[]` on all rows.
- **Append only** after salesperson confirms account/opportunity and approves save.
- Do **not** overwrite `meeting_transcript` / other pre-generated meeting columns when saving an
  upload.
- Binary files live in **object storage** (e.g. Supabase Storage). JSONB stores metadata + text +
  extractions + storage path — not the file bytes.

Recommended element shape (event implementation may add fields but should keep these):

```json
{
  "meeting_id": "uuid-or-text",
  "account_id": "ACC-0181",
  "opportunity_id": "OPP-0181",
  "uploaded_file_name": "ACC-0181_followup_call_2026-10-28.txt",
  "uploaded_file_type": "txt",
  "storage_path": "meetings/ACC-0181/…",
  "upload_date": "2026-11-04T12:00:00Z",
  "transcript": "…",
  "meeting_summary": "…",
  "customer_requirements": [],
  "budget_discussion": "…",
  "pain_points": [],
  "objections": [],
  "stakeholders": [],
  "competitor_mentions": [],
  "action_items": [],
  "customer_commitments": [],
  "deadlines": [],
  "recommended_next_steps": [],
  "processing_status": "saved",
  "data_classification": "SYNTHETIC"
}
```

Demo upload target prepared on disk: account `ACC-0181`
(`backend/data/crm_master/sample_meetings/`).

### 5.4 `proposal_draft` (object)

Includes `requires_human_approval: true`, `status_note`, title, and outline sections. Status for
sending/sharing is `proposal_status` / `followup_message_status`, not “sent by the system.”

### 5.5 Handoff JSONB

`implementation_requirements`, `delivery_commitments`, `handoff_stakeholders`,
`implementation_risks`, `onboarding_checklist` — structured lists for F6 on `deal_status = won`
rows (`handoff_required = true`).

### 5.6 `product_reference` / `field_classification` / `institution_verification`

- `product_reference`: array of official product claim objects (`product_name`, `claim_text`,
  `source_url`, `verified_on`, `classification`).
- `field_classification`: map of field-group → `PUBLIC_VERIFIED` | `SYNTHETIC` | `AI_GENERATED`.
- `institution_verification`: how the official website was checked.

### 5.7 `supporting_document_reference` (text)

Blocker rows point at knowledge-base document ids (e.g. `KB-SEC-01 …`). Files live under
`backend/data/crm_master/knowledge_base/`. They are **not** rows in `crm_master`.

---

## 6. Constraints and indexes

### 6.1 Table CHECKs (from DDL)

- `record_segment` ∈ `early_lead`, `qualified_lead`, `active_opportunity`, `stalled_at_risk`,
  `lost_inactive`, `won`
- `data_classification` / `record_data_classification` ∈ `PUBLIC_VERIFIED`, `SYNTHETIC`,
  `AI_GENERATED`
- `risk_category` / `account_priority` null or ∈ `high`, `medium`, `low`
- `signal_classification` null or ∈ `PUBLIC_VERIFIED`, `SYNTHETIC`
- If `signal_classification = PUBLIC_VERIFIED` then `signal_source_url` is not null
- Score columns 0–100; `deal_value` ≥ 0; `inactivity_days` ≥ 0 where constrained

### 6.2 Indexes (existing)

B-tree on: `record_segment`, `country`, `institution_category`, `account_priority`,
`opportunity_stage`, `deal_status`, `risk_category`, `expected_close_date`, `next_followup_date`,
`inactivity_days`, `recovery_eligibility`, `(signal_detected, signal_classification)`,
`(blocker_detected, blocker_status)`, `(handoff_required, handoff_status)`, `account_name`.

GIN on: `stakeholders`, `customer_requirements`.

---

## 7. Feature write rules (event coding)

| Feature | Read | Write (only with human action where noted) |
|---|---|---|
| F1 Recovery | `deal_status` in lost/inactive, `recovery_eligibility`, signals, drafts | On approved “sent/sync”: append `activity_history`, update last-contact fields, draft status. **Do not** auto-reopen or mark recovered |
| F2 Risk | open/stalled + `revenue_risk_score`, reasons, blockers | Recompute scores in code if needed; store explanation text carefully |
| F3 Meeting | pre-generated meeting_* ; sample files | Append `uploaded_meetings` after confirm/approve; optional approved merge into requirement fields |
| F4 Blocker | `blocker_*`, `supporting_document_reference`, KB files | Store answer drafts as AI output pending approval (column or response-only until API is fixed). Do not invent citations |
| F5 Drafts | requirements, product_reference, followup/proposal fields | Update draft bodies/status on edit/approve/reject only |
| F6 Handoff | won rows + handoff JSONB | Generate/refresh handoff when user marks won or requests handoff; never mark won only because a draft exists |

**Forbidden:** creating additional CRM tables; storing upload binaries in JSONB; deleting
pre-generated meeting columns when uploading; claiming PUBLIC_VERIFIED for invented URLs.

---

## 8. Knowledge base and vectors

| Item | MVP decision |
|---|---|
| Source files | `backend/data/crm_master/knowledge_base/*.md` (21 documents) |
| In `crm_master`? | No document bodies |
| Embeddings | **Not loaded yet.** At event: chunk + embed (`text-embedding-ada-002`, 1536 dims pending verify) |
| Storage for vectors | Prefer a **non-CRM** table such as `revenue_recovery.kb_chunks` (`doc_id`, `chunk_id`, `content`, `embedding vector(1536)`, metadata). Do not put embeddings on `crm_master` |
| Salesperson PDF upload | Store file in object storage; chunk/embed into the same KB chunk store with `source = salesperson_upload`; cite separately from official excerpts |

Exact cosine search over a small chunk set is enough (no IVFFlat required for MVP size).

---

## 9. Auth-related table (optional companion)

`crm_master` does not store Clerk users. If authentication is implemented as in
`docs/AUTHENTICATION.md`, add **only**:

`revenue_recovery.app_users` — `clerk_user_id`, email, role fixed to `SALES_REP`, timestamps.

No per-user row filtering on `crm_master` in the MVP (one rep sees all demo rows).

---

## 10. Import, reset, and migrations

| Topic | MVP reality |
|---|---|
| Import from CSV/JSON sample pack | **Not used.** Data already loaded |
| Reset that truncates many tables | **Not applicable** to the old multi-table plan |
| Rebuild | Only if explicitly requested: re-run DDL from `schema.sql` and a controlled reload |
| Alembic | Optional for event. If used: version table in `revenue_recovery`; never migrate other schemas |
| Changing columns | Update `schema.sql` **and this document** before altering production Supabase |

---

## 11. Mapping to API (until `API_CONTRACT.md` is revised)

| API concept (old docs) | MVP source |
|---|---|
| Company / account | `crm_master` account_* columns; key `account_id` |
| Deal / opportunity | same row; keys `opportunity_id`, `deal_status`, value/stage/close |
| Contact | contact_* on same row |
| Activity timeline | `activity_history` + activity_* summary fields |
| Score / risk | `revenue_risk_score`, `risk_category`, `risk_reason` |
| Meeting | `meeting_*` and/or `uploaded_meetings[]` |
| Blocker | `blocker_*` + KB retrieval |
| Draft / proposal / follow-up | `followup_*`, `proposal_*`, `proposal_draft` |
| Handoff | handoff_* and related JSONB on won rows |
| Dashboard aggregates | SQL over `crm_master` filters (`record_segment`, `deal_status`, `risk_category`, …) |

---

## 12. Demo anchors (data already loaded)

| Purpose | Account | Notes |
|---|---|---|
| F1 recovery + PUBLIC_VERIFIED signal | `ACC-0178` ASU, `ACC-0180` CSU, `ACC-0189` Ohio State | `recovery_eligibility = eligible` |
| F3 live upload | `ACC-0181` Georgia Institute of Technology | Sample files on disk; `uploaded_meetings = []` |
| F2 high risk | e.g. stalled high `revenue_risk_score` rows | Filter `deal_status` open/stalled, `risk_category = high` |
| F6 handoff | any `deal_status = won` | 25 packed handoff rows |

---

## Open questions

1. Confirm embedding dimensions for the configured Azure deployment (`1536` expected).
2. Confirm whether `app_users` is created in Phase 1 or Clerk is verified without a local user row.
3. Confirm Supabase Storage bucket name for meeting/KB uploads.
4. When `API_CONTRACT.md` is updated, replace `deal_001`-style examples with `account_id` /
   `opportunity_id` from this table.
5. Align `docs/DATA_SOURCES.md` and `docs/IMPLEMENTATION_PLAN.md` to “data preloaded; no CSV
   import phase” in a follow-up edit.

---

## Document history

| Date | Change |
|---|---|
| 2026-11-04 | Replaced multi-table design with live `crm_master` single-table MVP design |
