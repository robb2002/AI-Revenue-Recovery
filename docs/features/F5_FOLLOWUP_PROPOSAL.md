# Feature 5 PRD — Follow-up & Proposal Generator

**Status:** READY FOR EVENT IMPLEMENTATION  
**Feature key:** `proposal_generator`  
**Owner folders:** FE `frontend/src/pages/f5_drafts/` (+ optional `features/f5_drafts/`);  
BE `backend/app/api/routes/f5_drafts.py`, `backend/app/services/f5_drafts.py`  
**Branch:** `feat/f5-drafts`

---

## 0. How to use this PRD

1. Read `docs/features/README.md` (parallel module rules — **mandatory**).  
2. UI: `docs/UI_UX_DESIGN.md` only (Premium Hybrid — same as F1–F4).  
3. APIs: `docs/API_CONTRACT.md` §10.  
4. Data: `docs/DATABASE_DESIGN.md` (draft / proposal / follow-up columns).  
5. Grounding: `docs/AI_RAG_DESIGN.md` (no invented prices/capabilities).  
6. Demo anchors: `docs/DATA_SOURCES.md`; strong account `ACC-0181` after F3/F4.  
7. Do **not** generate automated test files unless asked.

F5 must not implement F1 re-engagement email-sync, F6 mark-won, or F4 retrieval inside its
module (it may **read** approved blocker answers / meeting extractions as inputs).

---

## 1. Goal (judge-facing)

Produce a **tailored follow-up email** and/or **proposal outline** from stored requirements,
objections, product references, and meeting context. Everything stays in **`draft`** until the
salesperson **approves or rejects**. Approval **does not send** email and **does not** mark the
deal won.

**One-line pitch:** “First drafts in minutes — you still own every word that leaves the building.”

---

## 2. Parallel development contract (F5-specific)

| Area | F5 owns | Must not modify |
|---|---|---|
| Routes UI | `/accounts/:accountId/drafts` | F1 recovery drafts UI; F6 handoff pages |
| API | `/accounts/{id}/drafts*` followup + proposal | `/drafts/reengagement` (F1), handoff (F6) |
| Services | Follow-up + proposal generate/patch/approve; completeness check | Risk score, KB index, meeting save |
| Shared | Read `crm_master`; write only F5 draft columns | No new CRM tables |

**Commit hygiene:** F5 folders only (+ shared draft editor component if Platform agrees).

---

## 3. User stories

1. As a rep, I open Drafts on an account and see existing follow-up / proposal state.  
2. As a rep, I generate a follow-up email from requirements + last meeting context.  
3. As a rep, I generate a proposal outline using only confirmed needs + `product_reference`.  
4. As a rep, I edit while `draft`, then approve or reject.  
5. As a rep, I see **open questions / completeness gaps** (decision maker, open blockers, unknown
   requirements).  
6. As a rep, I never see a Send button; approved means “ready for me to use outside the app.”

---

## 4. Scope

### 4.1 In scope (MVP must)

- GET drafts payload for an account.  
- Generate/refresh **follow-up email** (`followup_email_subject`, `followup_email_body`,
  `followup_message_status`).  
- Generate/refresh **proposal outline** (`proposal_title`, `proposal_draft` jsonb,
  `proposal_status`, related summary fields).  
- PATCH while state is `draft`.  
- Approve / reject (state only).  
- Completeness panel: missing decision-maker, open blockers, unconfirmed requirements, pricing
  unknowns.  
- Guardrails: no invented $, discounts, or capabilities not in `product_reference` / confirmed
  requirements / approved KB facts supplied in the prompt package.  
- Premium Hybrid UI: light AI surface for long drafts; indigo Generate; navy primary; green
  approved; neutral rejected.  
- `DraftNotice` + `ApprovalBar` on every draft.

### 4.2 Out of scope

- SMTP / real send.  
- Mark won / handoff (F6).  
- F1 re-engagement sync (different draft type + flow).  
- Full PDF export (nice-to-have).  
- Automated tests.  
- Creating a separate `drafts` CRM table (use `crm_master` columns).

### 4.3 Should-have

- Side-by-side “sources used” chips (requirement ids, product_reference, meeting upload id).  
- One-click insert of F4-approved answer blurb into follow-up (read-only paste assist).  
- Version note in `proposal_draft` when regenerated.

---

## 5. Data (`crm_master`)

### 5.1 Read

| Column | Use |
|---|---|
| `account_id`, `account_name`, `opportunity_*`, `deal_value`, `deal_status` | Context |
| `contact_name`, `contact_designation`, `account_owner` | Email greeting / signer |
| `customer_requirements`, `customer_requirements_summary` | Core inputs |
| `pain_points`, `customer_objections`, `decision_criteria` | Outline sections |
| `budget_discussion`, `purchase_timeline` | Open questions if unconfirmed |
| `product_interest`, `recommended_products`, `recommended_solution` | Solution section |
| `product_reference` | **Only** allowed product claim texts + URLs |
| `value_proposition` | Seed / refresh |
| `blocker_category`, `blocker_status`, `blocker_description` | Completeness / open questions |
| `meeting_summary`, `uploaded_meetings` (latest) | Recency context |
| `followup_*`, `proposal_*`, `proposal_draft` | Existing drafts |
| `is_decision_maker` | Completeness |
| `as_of_date` | Clock |

### 5.2 Write (F5 only)

| Action | Columns |
|---|---|
| Generate follow-up | `followup_email_subject`, `followup_email_body`, `followup_message_status=draft`, `next_followup_recommendation` optional |
| Generate proposal | `proposal_generated=true`, `proposal_title`, `proposal_draft`, `proposal_status=draft`, refresh `customer_requirements_summary` / `value_proposition` / `recommended_*` if derived safely from stored data |
| PATCH | subject/body/sections while draft |
| Approve | `followup_message_status` or `proposal_status` → `approved` |
| Reject | → `rejected` |

**Never:** `deal_status` won/lost; send flags; invent commercial terms.

### 5.3 `proposal_draft` shape (keep/extend)

```json
{
  "classification": "AI_GENERATED",
  "simulated": true,
  "requires_human_approval": true,
  "status_note": "Draft. Not sent. Human review and approval required.",
  "title": "…",
  "executive_summary": "…",
  "customer_requirements": ["…"],
  "proposed_solution": "…",
  "engagement_outline": ["…"],
  "commercial_note": "Pricing requires approved quote — not stated here.",
  "open_questions": ["…"],
  "assumptions": ["…"],
  "next_steps": ["…"],
  "sources_used": [{ "type": "product_reference|requirement|meeting|blocker", "ref": "…" }]
}
```

### 5.4 Demo accounts

| Account | Why |
|---|---|
| `ACC-0181` | Best connected demo after F3/F4 (requirements + integration facts) |
| Any open with `proposal_status=draft` | Pre-seeded outlines exist (~89 open/stalled with proposal_draft) |
| Won with `proposal_status=approved` | Show read-only approved state (no edit) |

---

## 6. Backend design

### 6.1 Modules

```
api/routes/f5_drafts.py
services/f5_drafts.py
services/f5_completeness.py   # pure rules
```

### 6.2 Responsibilities

| Method | Behavior |
|---|---|
| `get_drafts` | Read follow-up + proposal fields |
| `generate_followup` | Build prompt package → AI → validate → write draft columns |
| `generate_proposal` | Same for outline; force commercial_note without prices |
| `patch_draft` | Only if state draft |
| `approve` / `reject` | State transition; reject body immutable after |
| `completeness` | Code list of missing items |

### 6.3 Completeness rules (code)

Flag missing when:

- `is_decision_maker` is false / unknown decision maker in stakeholders  
- Open blocker (`blocker_status` in `open`,`in_progress`)  
- Any requirement `status=unconfirmed` or `unknown`  
- No `product_reference` entries  
- Budget language says not approved / unknown  

Return `{ complete: bool, missing: string[] }` on GET and after generate.

### 6.4 API

| Method | Path |
|---|---|
| GET | `/accounts/{id}/drafts` |
| POST | `/accounts/{id}/drafts/followup` |
| POST | `/accounts/{id}/drafts/proposal` |
| PATCH | `/accounts/{id}/drafts/followup` or `/proposal` |
| POST | `/accounts/{id}/drafts/followup/approve` \| `/reject` |
| POST | `/accounts/{id}/drafts/proposal/approve` \| `/reject` |

`draft_type` values: `followup_email`, `proposal_outline` (F1 owns `reengagement_email`).

### 6.5 Validation (defect prevention)

- Every product capability sentence must map to `product_reference.claim_text` or a confirmed
  requirement string.  
- No currency amounts unless present in supplied CRM fields (and still not as “quoted price”
  unless explicitly a stored quote — prefer commercial_note).  
- Forbidden phrases: guaranteed, will close, send, recovered.  
- After approve/reject: PATCH → `409 STATE_NOT_EDITABLE`.

---

## 7. Frontend design

### 7.1 Route

`/accounts/:accountId/drafts`  
Nav under account / **Drafts** icon `FilePen`.

### 7.2 Visual system

| Element | Token |
|---|---|
| Generate | `indigo-600` + Sparkles |
| Save edits | `navy-600` |
| Approved pill | `green-600` |
| Rejected pill | neutral |
| Draft surface | `surface-ai-subtle` |
| Completeness warnings | amber-50 panel |
| DraftNotice | always visible |

### 7.3 Layout

**Tabs:** Follow-up email | Proposal outline  

**Left/main:** editor (subject + body or sectioned outline).  
**Right rail:** Completeness / open questions; Sources used; Account snapshot.  
**Bottom:** ApprovalBar.  

Empty: “Generate a draft to get started.”  
Approved: read-only with approved timestamp.  

### 7.4 States

Loading, generating, AI unavailable (show last stored draft), validation error (strip bad
claims), approve success toast (“Approved — nothing was sent”).

---

## 8. Scenarios (must pass)

1. ACC-0181 generate follow-up mentions Canvas/requirements; no fake discount.  
2. Generate proposal lists open security/budget questions if blockers open.  
3. Edit → save → approve → cannot edit.  
4. Reject → regenerate allowed.  
5. AI down → pre-seeded proposal_draft still viewable.  
6. Completeness shows missing decision-maker when `is_decision_maker=false`.  
7. No Send control anywhere.  
8. Approve does not change `deal_status`.

---

## 9. Guardrails

- Human approval required.  
- No send / no mark won.  
- No invented catalog or prices.  
- Fictional demo label.  
- Shared Premium Hybrid theme.  
- Isolated F5 modules.

---

## 10. Acceptance criteria (manual)

1. Both draft types generate and persist on `crm_master`.  
2. Completeness panel accurate.  
3. Approve/reject state machine correct.  
4. Grounding guards block unknown capabilities/prices.  
5. UI matches design system.  
6. Works on ACC-0181 demo path.  
7. Code isolation respected.

---

## 11. Demo script (~1.5–2 min)

1. From Georgia Tech after F3/F4 → Drafts.  
2. Generate follow-up — show personalization + “not sent”.  
3. Generate proposal — open questions include budget committee.  
4. Approve proposal — green pill.  
5. Bridge: “When we mark won, Feature 6 packs this into handoff.”

---

## 12. Dependencies

| Need | From |
|---|---|
| Auth, shell | Platform |
| Requirements / meetings | F3 data on row |
| Blocker open flags | Preloaded / F4 |
| Mark won | F6 |

---

## 13. Open questions

1. Whether approve follow-up should offer F1-style “sync email to CRM” or leave that to F1 only —
   **recommend:** F5 approve ≠ CRM activity sync; optional “Log follow-up sent” can deep-link F1
   pattern later.  
2. Max proposal section length.

---

## Document history

| Date | Change |
|---|---|
| 2026-11-04 | Initial F5 feature PRD |
