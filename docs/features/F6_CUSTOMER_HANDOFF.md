# Feature 6 PRD — Customer Handoff

**Status:** READY FOR EVENT IMPLEMENTATION  
**Feature key:** `handoff`  
**Owner folders:** FE `frontend/src/pages/f6_handoff/` (+ optional `features/f6_handoff/`);  
BE `backend/app/api/routes/f6_handoff.py`, `backend/app/services/f6_handoff.py`  
**Branch:** `feat/f6-handoff`

---

## 0. How to use this PRD

1. Read `docs/features/README.md` (parallel module rules — **mandatory**).  
2. UI: `docs/UI_UX_DESIGN.md` only (Premium Hybrid — same as F1–F5).  
3. APIs: `docs/API_CONTRACT.md` §11.  
4. Data: `docs/DATABASE_DESIGN.md` (`handoff_*`, `deal_status`).  
5. Grounding: `docs/AI_RAG_DESIGN.md`.  
6. Demo: mark-won path on a staged open account (e.g. after F5 on ACC-0181) **or** open a
   pre-seeded `deal_status=won` row with `handoff_required=true`.  
7. Do **not** generate automated test files unless asked.

F6 is the **only** feature allowed to set `deal_status=won` (via explicit mark-won). It must not
implement F1 recovery, F2 scoring, F3 upload, F4 RAG, or F5 draft generation (it **reads** approved
drafts / requirements / meetings as handoff inputs).

---

## 1. Goal (judge-facing)

When a deal is **explicitly marked won**, generate a **structured customer handoff pack** for
delivery: stakeholders, confirmed requirements, open items, timeline, approved proposal summary,
and product references. Human reviews and **approves** the pack. The system does **not** email
delivery or create tickets outside the app.

**One-line pitch:** “Won means handoff-ready — sales packs the context delivery needs, without
inventing scope.”

---

## 2. Parallel development contract (F6-specific)

| Area | F6 owns | Must not modify |
|---|---|---|
| Routes UI | `/accounts/:accountId/handoff`, mark-won control | F5 drafts editors |
| API | `/mark-won`, `/handoff/*` | F5 draft generate, F1 reopen |
| Services | Mark won, generate handoff, approve handoff | Risk/recovery scoring, KB |
| Shared | Read CRM; write `deal_status`, `handoff_*`, activity note | New CRM tables |

**Commit hygiene:** F6 folders only.

---

## 3. User stories

1. As a rep, I can **mark a deal won** only with an explicit confirm checkbox.  
2. As a rep, after won, I see handoff is required and can generate the pack.  
3. As a rep, I review sections (stakeholders, requirements, open items, next steps) and approve.  
4. As a rep, I cannot mark won just because a proposal draft exists.  
5. As a rep, generate on non-won → clear error.  
6. As a rep, I understand at-risk value and handoff are different concepts (no “recovered” copy).

---

## 4. Scope

### 4.1 In scope (MVP must)

- `POST mark-won` with `{ confirm: true }` → `deal_status=won`, `handoff_required=true`,
  set `closed_date` if empty to `as_of_date` / DEMO clock, append activity note.  
- GET handoff pack fields.  
- POST generate/refresh structured handoff → store `handoff_pack` (jsonb) + status `draft`.  
- POST approve handoff → `handoff_status=approved` (or product enum equivalent).  
- UI sections: Account summary, Stakeholders, Confirmed requirements, Open items / risks for
  delivery, Timeline, Product references, Proposal summary (if approved), Human notes.  
- Premium Hybrid: green for won/approved; navy primary Mark won; indigo Generate; amber for open
  delivery risks.  
- Guardrails: no invented commitments; copy from CRM + approved drafts only.

### 4.2 Out of scope

- Jira / ServiceNow / email to CS.  
- Auto mark won from proposal approve.  
- Changing lost → won without confirm.  
- Automated tests.  
- Separate handoff CRM table (columns on `crm_master`).

### 4.3 Should-have

- Export handoff as markdown download.  
- Diff “regenerated vs previous” notice.  
- Deep link from dashboard “Handoffs pending” count.

---

## 5. Data (`crm_master`)

### 5.1 Read (for pack)

| Column | Use |
|---|---|
| Account / opportunity / value / dates | Header |
| Contacts, stakeholders, `is_decision_maker` | Stakeholders section |
| `customer_requirements` (confirmed preferred) | Requirements |
| `pain_points`, `customer_objections` | Context / open risks |
| `blocker_*` if still open | Open items |
| `purchase_timeline`, `implementation_notes` | Timeline |
| `product_reference`, `recommended_products` | Products |
| `proposal_draft` if `proposal_status=approved` | Proposal summary |
| `meeting_summary`, latest `uploaded_meetings` | Context |
| `handoff_*` | Existing pack |

### 5.2 Write

| Action | Columns |
|---|---|
| Mark won | `deal_status=won`, `handoff_required=true`, `closed_date` if needed, `updated_at`, activity note in `activity_history` |
| Generate | `handoff_pack`, `handoff_status=draft`, `handoff_generated_at`, maybe `handoff_summary` |
| Approve | `handoff_status=approved`, `handoff_approved_at` |

**Never:** set won because draft approved; invent delivery dates or SLAs.

### 5.3 `handoff_pack` shape

```json
{
  "classification": "AI_GENERATED",
  "simulated": true,
  "requires_human_approval": true,
  "account_id": "ACC-…",
  "opportunity_name": "…",
  "stakeholders": [{ "name": "…", "role": "…", "is_decision_maker": true }],
  "confirmed_requirements": ["…"],
  "open_items": ["…"],
  "timeline": ["…"],
  "products": [{ "name": "…", "reference_url": "…" }],
  "proposal_summary": "… or null",
  "delivery_notes": "…",
  "evidence": [{ "source_type": "…", "snippet": "…" }]
}
```

### 5.4 Demo accounts

| Account | Why |
|---|---|
| Pre-seeded `won` + `handoff_required` | Instant handoff demo without mark-won |
| ACC-0181 (open) | Full journey: mark won → generate → approve |
| Lost account | Mark-won must refuse or require explicit product rule (recommend **refuse** lost → won without separate reopen) |

---

## 6. Backend design

### 6.1 Modules

```
api/routes/f6_handoff.py
services/f6_handoff.py
```

### 6.2 Methods

| Method | Behavior |
|---|---|
| `mark_won` | Require `confirm:true`; only from `open` (and optionally `postponed` if product allows — default **open only**); set won + handoff_required |
| `get_handoff` | Return pack + status; 404 if none |
| `generate` | Require `deal_status=won`; else `409 DEAL_NOT_WON`; build pack from CRM; LLM may polish wording only from supplied facts |
| `approve` | Require draft pack exists |

### 6.3 API

| Method | Path |
|---|---|
| POST | `/accounts/{id}/mark-won` |
| GET | `/accounts/{id}/handoff` |
| POST | `/accounts/{id}/handoff/generate` |
| POST | `/accounts/{id}/handoff/approve` |

Errors: `409 DEAL_NOT_WON`, `409 ALREADY_WON`, `400 CONFIRM_REQUIRED`, `409 HANDOFF_NOT_DRAFT`.

### 6.4 Validation

- Mark won without confirm → 400.  
- Generate if not won → 409.  
- Pack sections empty if no evidence → list “unknown / not in CRM” rather than invent.  
- Proposal summary included only if `proposal_status=approved`.

---

## 7. Frontend design

### 7.1 Routes

- `/accounts/:accountId/handoff`  
- Mark won control also on account overview (Platform or F6 component registered there).

Nav: **Handoff** icon `Handshake`.

### 7.2 Visual system

| Element | Token |
|---|---|
| Mark won button | navy-600 (destructive-confirm pattern: require checkbox) |
| Won badge | green-600 |
| Generate | indigo-600 |
| Open delivery risks | amber-50 |
| Approved pack | green border / pill |
| DraftNotice | on generated pack |

### 7.3 Layout

**If not won:** banner “Deal not won — mark won to enable handoff” + Mark won dialog.  
**If won, no pack:** empty state + Generate.  
**If pack draft:** sectioned review + Approve.  
**If approved:** read-only pack + download (should-have).

### 7.4 Mark won dialog

- Checkbox: “I confirm this deal is won. This does not send email.”  
- Confirm disabled until checked.  
- Success: toast + navigate to handoff.

---

## 8. Scenarios (must pass)

1. Mark won on open ACC-0181 → status won, handoff_required true.  
2. Generate pack includes stakeholders + confirmed requirements only.  
3. Open blockers appear under open_items.  
4. Approve → green approved.  
5. Generate while still open → 409 shown in UI.  
6. Proposal approve alone does **not** set won.  
7. Pre-seeded won account: open handoff without mark-won.  
8. No send / no ticket create.

---

## 9. Guardrails

- Explicit human mark-won.  
- Handoff is draft until approved.  
- No invented SLAs / go-lives.  
- Won ≠ recovered; do not show recovery metrics as handoff success.  
- Fictional demo label.  
- Shared Premium Hybrid.  
- Isolated F6 modules.

---

## 10. Acceptance criteria (manual)

1. Mark-won path works with confirm.  
2. Handoff generate blocked until won.  
3. Pack grounded in CRM + approved proposal.  
4. Approve state machine correct.  
5. UI tokens correct.  
6. Demo works on pre-seeded won **and** mark-won journey.  
7. Code isolation respected.

---

## 11. Demo script (~1–1.5 min)

1. After F5 on ACC-0181 (or jump to pre-seeded won).  
2. Mark won with confirm.  
3. Generate handoff — show stakeholders + open items.  
4. Approve — “ready for delivery discussion.”  
5. Close: “Six features, one workflow — evidence in, human out.”

---

## 12. Dependencies

| Need | From |
|---|---|
| Auth, shell, account overview slot | Platform |
| Requirements / meetings | F3 |
| Proposal summary | F5 (optional but better demo) |
| Blockers | Preload / F4 |

---

## 13. Open questions

1. Allow mark-won from `postponed`? Default no.  
2. Allow regenerating after approve (creates new draft)? Recommend yes with status reset to draft.

---

## Document history

| Date | Change |
|---|---|
| 2026-11-04 | Initial F6 feature PRD |
