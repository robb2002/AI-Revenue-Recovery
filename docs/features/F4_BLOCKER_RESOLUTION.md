# Feature 4 PRD — Deal Blocker Resolution Agent

**Status:** READY FOR EVENT IMPLEMENTATION  
**Feature key:** `blocker_resolution`  
**Owner folders:** FE `frontend/src/pages/f4_blockers/` (+ optional `features/f4_blockers/`,
`pages/f4_knowledge/`);  
BE `backend/app/api/routes/f4_blockers.py`, `backend/app/services/f4_blockers.py`,  
`backend/app/ai/retrieval.py`, `backend/app/ai/kb_indexer.py`  
**Branch:** `feat/f4-blockers`

---

## 0. How to use this PRD

1. Read `docs/features/README.md` (parallel module rules — **mandatory**).  
2. UI: `docs/UI_UX_DESIGN.md` only (Premium Hybrid).  
3. APIs: `docs/API_CONTRACT.md` §9.  
4. CRM blockers: `docs/DATABASE_DESIGN.md`; KB files: `backend/data/crm_master/knowledge_base/`.  
5. Planted Q&A: `knowledge_base/README.md`. Grounding: `docs/AI_RAG_DESIGN.md`.  
6. Do **not** generate automated test files unless asked.

F4 owns KB indexing/retrieval. F3 may deep-link here; F4 must not own meeting upload.

---

## 1. Goal (judge-facing)

Answer a customer’s **deal blocker question** using **approved knowledge documents**, show
**verbatim citations**, and support **answered / partially_answered / insufficient_evidence**.
The salesperson **approves or rejects** the draft answer before it is treated as ready to share.
Nothing is sent automatically. No invented prices, certifications, or hosting claims.

**One-line pitch:** “If we don’t have it in the approved docs, we say so — with a next step.”

---

## 2. Parallel development contract (F4-specific)

| Area | F4 owns | Must not modify |
|---|---|---|
| Routes UI | `/accounts/:accountId/blockers`, `/knowledge` | F1–F3, F5–F6 pages |
| API | blocker get/answer/approve/reject; knowledge list/upload/index | Meeting save, risk score, drafts |
| Services | Chunk, embed, retrieve, gate, answer, citation validate | `uploaded_meetings` writes |
| Shared | Read `crm_master` blocker fields; optional `kb_chunks` table | Do not put document bodies into `crm_master` |

**Commit hygiene:** F4 modules + migration for `kb_chunks` only (non-CRM).

---

## 3. User stories

1. As a rep, I open an account and see the **open blocker** (category, description, KB doc hint).  
2. As a rep, I ask a natural-language question and get a **draft answer with citations**.  
3. As a rep, I see clear status when evidence is partial or missing.  
4. As a rep, I **approve/reject** the draft; approve ≠ send.  
5. As a rep, I can browse indexed KB documents.  
6. As a rep (should-have), I upload a PDF/DOCX for this deal as extra retrieval context.  

---

## 4. Scope

### 4.1 In scope (MVP must)

- Load blocker context from `crm_master` for an account.  
- Index all 21 markdown files under `knowledge_base/` into embeddings (`kb_chunks` or equivalent).  
- Retrieve top-k chunks with similarity gate; if below gate → `insufficient_evidence` **without**
  calling the chat model (`model_called: false`).  
- Generate grounded answer with citations (`doc_id`, title, snippet, optional `source_url`).  
- Three statuses: `answered` | `partially_answered` | `insufficient_evidence`.  
- Approve / reject draft answer (state only).  
- Planted demo questions from KB README must behave as designed.  
- UI: BlockerAnswerCard, InsufficientEvidenceNotice, EvidenceDrawer, ApprovalBar.  
- Honesty: SOC2 “support compliance” ≠ product certified; hosting product-specific; pricing → escalate.

### 4.2 Out of scope

- Open web search / user-supplied arbitrary URLs to crawl.  
- Inventing list prices or SLA minutes.  
- Auto-emailing the customer.  
- Resolving blocker_status to `resolved` without explicit user action (optional confirm later).  
- Storing full Pearson pages (excerpts only, already in files).  
- Automated tests.

### 4.3 Should-have

- `POST /knowledge/upload` salesperson docs → Storage → chunk/embed with
  `source=salesperson_upload`.  
- Suggest starter questions from `blocker_category`.  
- After approve, optional preview to set `blocker_status` to `in_progress` (confirm required).

---

## 5. Data

### 5.1 CRM read (`crm_master`)

| Column | Use |
|---|---|
| `account_id`, `account_name`, `opportunity_id` | Context |
| `blocker_detected`, `blocker_category`, `blocker_description` | Primary context |
| `blocker_severity`, `blocker_status`, `blocker_owner` | Display |
| `blocker_resolution_deadline` | Display |
| `required_documentation`, `supporting_document_reference` | Hint which KB id |
| `suggested_resolution` | Optional seed for question |
| `deal_status`, `product_interest` | Context for phrasing |
| `as_of_date` | Clock |

### 5.2 CRM write (minimal)

| Action | Write |
|---|---|
| Answer draft | Prefer side store: response id in memory/table `blocker_answer_drafts` **or** jsonb
  `blocker_answers` array on row — **decide one**. Recommend: jsonb
  `blocker_answer_drafts` append-only on `crm_master` **or** ephemeral + approve writes
  `suggested_resolution` only. Simplest defect-free MVP: **persist draft in
  `crm_master` jsonb column `blocker_answer_history`** if added via ALTER; if no migration time,
  keep draft in backend session/DB table `revenue_recovery.blocker_answer_drafts` (non-CRM
  entity table — allowed like `kb_chunks`). |
| Approve/reject | Update draft `state` only |
| Optional | `blocker_status` → `in_progress` with confirm |

Do **not** invent a second CRM account table.

### 5.3 Knowledge files (must index)

Path: `backend/data/crm_master/knowledge_base/*.md`  
Ids: `KB-OFF-01`…`10`, `KB-PRC-01`, `KB-PRD-02`, `KB-SEC-01`, `KB-INT-01`, `KB-PRO-01`,
`KB-LGL-01`, `KB-BUD-01`, `KB-STK-01`, `KB-IMP-01`, `KB-SUP-01`, `KB-CMP-01`.

Chunk boundary: each `##` section. Keep front matter as metadata (`doc_id`, `title`, `version`).

### 5.4 Planted questions (must pass)

| Question | Expected `answer_status` | Primary docs |
|---|---|---|
| Works with Brightspace (D2L)? | `answered` | KB-OFF-01 |
| Grades MyLab → LMS? | `answered` (one-way) | KB-OFF-02 |
| Grades LMS → MyLab? | `answered` (not described / one-way only) | KB-OFF-02 |
| Where is data hosted? | `partially_answered` | KB-OFF-05 |
| SAML/OIDC SSO? | `partially_answered` | KB-OFF-01, KB-INT-01 |
| Product SOC 2 certified? | `partially_answered` | KB-OFF-04, KB-SEC-01 |
| VPAT / accessibility? | `answered` | KB-OFF-07 |
| Discount for 5,000 learners? | `insufficient_evidence` | KB-PRC-01 |
| Guaranteed critical response time? | `insufficient_evidence` | KB-SUP-01 |
| Integrates with UnknownLMS9000? | `insufficient_evidence` | none |

### 5.5 Strong demo accounts

| Account | Why |
|---|---|
| `ACC-0181` | After F3 upload: Canvas/grade questions + budget blocker |
| `ACC-0041` / security blockers | KB-SEC-01 + OFF-04/05 |
| `ACC-0024` / integration | KB-INT-01 + OFF-01/02 |
| Pricing blocker rows | KB-PRC-01 → insufficient for a number |

---

## 6. Backend design

### 6.1 Modules

```
api/routes/f4_blockers.py
api/routes/f4_knowledge.py      # optional split
services/f4_blockers.py
ai/kb_indexer.py                # chunk + embed + upsert kb_chunks
ai/retrieval.py                 # similarity search + gate
```

### 6.2 `kb_chunks` (non-CRM, required for F4)

Suggested columns:

| Column | Type |
|---|---|
| `chunk_id` | uuid PK |
| `doc_id` | text |
| `title` | text |
| `section` | text |
| `content` | text |
| `source_url` | text null |
| `classification` | text |
| `source_kind` | `bundled_kb` \| `salesperson_upload` |
| `account_id` | text null (for uploads) |
| `content_hash` | text |
| `embedding` | vector(1536) |
| `created_at` | timestamptz |

Exact cosine `ORDER BY embedding <=> :q LIMIT k`. No IVFFlat required for ~few hundred chunks.

### 6.3 Answer pipeline

```
question (+ blocker context)
 → embed question
 → retrieve top-k
 → if max similarity < GATE → insufficient_evidence (no chat)
 → else chat with passages only
 → validate citations (handles + verbatim snippet substring)
 → compute answer_status in code
 → return draft state=draft
```

**Status rules (code, not model):**

- All asked facets covered by citations → `answered`  
- Some covered, some in “Not covered” / missing → `partially_answered`  
- No usable passages / below gate / pricing-SLA gap → `insufficient_evidence`  

### 6.4 API

| Method | Path | Notes |
|---|---|---|
| GET | `/accounts/{id}/blocker` | CRM blocker fields |
| POST | `/accounts/{id}/blocker/answer` | Body `{question}` → draft answer |
| POST | `/blocker-answers/{answer_id}/approve` | State approved |
| POST | `/blocker-answers/{answer_id}/reject` | State rejected |
| GET | `/knowledge/documents` | List doc_id, title, version |
| POST | `/knowledge/index` | Admin/event: reindex bundled markdown |
| POST | `/knowledge/upload` | Should-have multipart |

### 6.5 Citation validation (defect prevention)

- Every citation `snippet` must be substring of retrieved `content`.  
- `source_url` only if present on chunk metadata (OFF docs).  
- Reject model-supplied URLs not in input.  
- Forbidden phrases in answer unless inside a citation quote.  
- Never output a discount % or SLA minutes unless in chunk (they are not).

### 6.6 Indexing job

On event start (or first answer):

1. Read all `KB-*.md`.  
2. Split on `##`.  
3. Embed batches.  
4. Upsert by `content_hash`.  
5. Health: `GET /knowledge/documents` returns 21 bundled docs.

---

## 7. Frontend design

### 7.1 Routes

- `/accounts/:accountId/blockers`  
- `/knowledge` (document list + optional upload)

Nav: **Blockers** `HelpCircle`; Knowledge `BookOpen`.

### 7.2 Visual system

| Element | Token |
|---|---|
| Ask / Generate | `indigo-600` AI button |
| Primary navigation actions | `navy-600` |
| `answered` | green outline status |
| `partially_answered` | amber outline |
| `insufficient_evidence` | navy-tint notice (**not** red error) |
| Approve | green on ApprovalBar |
| Reject | neutral |
| Citations | EvidenceChip → drawer |

### 7.3 Blockers page layout

1. **Blocker summary card** — category, severity, description, supporting doc reference, deadline.  
2. **Starter chips** — from category (e.g. Integration → Brightspace, grade sync).  
3. **Question input** + Ask.  
4. **BlockerAnswerCard** — status pill, answer, citations, missing list, ApprovalBar.  
5. **InsufficientEvidenceNotice** when needed — missing items + recommended human route
   (Revenue Ops / Security).  
6. After approve — banner “Approved for salesperson use. Nothing was sent.”

### 7.4 Knowledge page

Table of doc_id, title, classification, categories. Optional upload dropzone (should-have).

### 7.5 States

Indexing in progress, KB not indexed, retrieval empty, AI fail after retrieval, approve success,
reject, upload unsupported type.

---

## 8. Scenarios (must pass)

1. Brightspace question → `answered` + KB-OFF-01 citation.  
2. MyLab grade sync direction → `answered` one-way; reverse clearly limited.  
3. Hosting question → `partially_answered`; no “all data in US” invention.  
4. SOC 2 certified product → `partially_answered`; no false certification.  
5. Discount amount → `insufficient_evidence`; model_called may be false if gate fails or after
   doc says escalate.  
6. Approve → state approved; still no send.  
7. Unindexed KB → clear UI error, no crash.  
8. ACC-0181 after F3: ask Canvas grade question from meeting context.  
9. (should-have) Upload PDF → appears in retrieval for that account only.

---

## 9. Guardrails

- No open web search.  
- No invented citations/URLs/prices/SLAs.  
- Human approve before “ready to share.”  
- insufficient_evidence is success path, not a red crash.  
- OFF excerpts stay attributed; synthetic docs labelled illustrative.  
- Fictional demo data on CRM chrome.  
- Same Premium Hybrid theme as other features.

---

## 10. Acceptance criteria (manual)

1. 21 KB docs indexed; list endpoint works.  
2. All planted questions hit expected status class (answered / partial / insufficient).  
3. Citations verbatim from chunks.  
4. Gate path can skip model.  
5. Approve/reject only change draft state.  
6. UI matches shared design system.  
7. F4 code isolation respected.  
8. No CRM multi-table creep; only `crm_master` reads + `kb_chunks` (+ optional draft table).

---

## 11. Demo script (~2 min)

1. From Georgia Tech (post-F3) open Blockers — budget + integration context.  
2. Ask: “Does grade sync work with Canvas / is it one-way?” → cited OFF-02.  
3. Ask: “What discount for 5,000 seats?” → insufficient_evidence → escalate.  
4. Approve the integration answer — “Not sent.”  
5. Bridge to F5: “Now draft the follow-up using confirmed requirements.”

---

## 12. Dependencies

| Need | From |
|---|---|
| Azure embeddings + chat | Platform / env |
| Storage for uploads | Platform |
| F3 meeting context | Optional deep-link |
| crm_master blockers | Preloaded data |

---

## 13. Open questions

1. Persist drafts in `blocker_answer_drafts` table vs jsonb on `crm_master`.  
2. Exact similarity gate value after calibration on this corpus.  
3. Embedding dimension confirm (`1536`).  
4. Salesperson upload in MVP or cut for time.

---

## Document history

| Date | Change |
|---|---|
| 2026-11-04 | Initial F4 feature PRD (F1/F2/F3 structure) |
