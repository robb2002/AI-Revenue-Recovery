# Implementation Plan — AI Revenue Recovery & Deal Intelligence Agent

**Status:** APPROVED FOR MVP BUILD — event-oriented, data preloaded (2026-11-04).  
**Supersedes:** import-first multi-table phase plan and Cedar Valley `deal_001` heroes.  
**Contracts:** `DATABASE_DESIGN.md`, `DATA_SOURCES.md`, `API_CONTRACT.md`, `UI_UX_DESIGN.md`,
`AUTHENTICATION.md`, `AI_RAG_DESIGN.md`, `TECHNICAL_PRD.md`, `PRODUCT_PRD.md`.

## Purpose of this document

Orders the event build, enables **parallel feature work** without merge chaos, defines manual
validation, cut order, and the demo script. **No phase starts until requested.** Validation is
manual; do not create test files unless asked.

---

## 1. Principles

1. **Data is ready.** Do not rebuild CSV import. Read/write `revenue_recovery.crm_master`.
2. **Killer path.** Recovery → risk → meeting upload → blocker answer → draft → mark won → handoff.
3. **Rules before AI.** Lists and scores work without a model call.
4. **Evidence and approval before polish.**
5. **One concern per branch / PR.**
6. **Documents win** (`AGENTS.md` §10). If code and docs disagree after this revision, update the
   outdated doc (API/UI/RAG still may need light follow-ups).
7. **No scope growth** for judge flash.

---

## 2. Time budget

Hackathon: **one day (≈24 hours)** of coding inside the event window unless rules say otherwise.  
`NEEDS VERIFICATION`: event rules on when code may be written/committed.

Demo runs on **localhost**: frontend **5173**, backend **8000** (same as closed parent app).

Pre-event (done): CRM load, KB markdown, sample meetings, Database/Data/API plan updates.

---

## 3. Team ownership (parallel)

| Area | Owner | Paths (convention) |
|---|---|---|
| Shared shell, auth, design tokens, API client | **Platform** (1 person) | `frontend/src/app`, `components/shell`, `api/client`; `backend/app/core`, `main` |
| F1 Recovery | Dev A | `docs/features/F1_LOST_LEAD_RECOVERY.md`; `frontend/.../f1_recovery`; `backend/.../routes/f1_*.py`, `services/f1_*` |
| F2 Risk | Dev B | `docs/features/F2_REVENUE_RISK_PRIORITIZER.md`; `f2_risk` / `f2_*` |
| F3 Meetings | Dev C | `docs/features/F3_MEETING_INTELLIGENCE.md`; `f3_meetings` / `f3_*` |
| F4 Blockers + KB ingest | Dev D | `docs/features/F4_BLOCKER_RESOLUTION.md`; `f4_blockers`, `ai/retrieval`; KB embed job |
| F5 Drafts | Dev E (or A after F1) | `docs/features/F5_FOLLOWUP_PROPOSAL.md`; `f5_drafts` / `f5_*` |
| F6 Handoff | Dev F (or B after F2) | `docs/features/F6_CUSTOMER_HANDOFF.md`; `f6_handoff` / `f6_*` |
| F7 Signal Scout | Stretch (after F1–F6) | `docs/features/F7_SIGNAL_SCOUT.md`; `f7_signal_scout` / `f7_*` |

**Conflict rules**

- Only Platform edits auth, router shell, Tailwind tokens, shared `AccountSummary` types.
- Feature owners do not rewrite `crm_master` schema; they use columns in `DATABASE_DESIGN.md`.
- Branch per feature: `feat/f1-recovery`, `feat/f2-risk`, … Merge often; keep PRs small.
- One shared OpenAPI/types file updated from `API_CONTRACT.md` by Platform when endpoints land.

If the team is smaller than six, pair F1+F5 and F2+F6; keep F3 and F4 staffed (demo-critical).

---

## 4. Phases

### Phase 0 — Pre-flight (S) — start of event

- [ ] Azure OpenAI chat + embeddings smoke test; record deployment names.
- [x] Confirm `vector` extension and schema `revenue_recovery` visible in Supabase.
- [x] `select count(*) from revenue_recovery.crm_master` = 200; spot-check F1 heroes and ACC-0181.
- [x] Clerk allows `http://localhost:5173`; keys in server/frontend env examples only.
- [x] Ports 5173 / 8000 free; Groq Whisper smoke (should-have audio).
- [x] KB folder and sample meetings present on disk.
- [ ] Google OAuth client for Gmail **readonly** (or confirm fixture-only demo path for F1).

Exit: open blockers recorded; build may start.

### Phase 1 — Foundations (M) — Platform

Backend: FastAPI app, config, async DB (`search_path=revenue_recovery`), errors, logging,
Clerk verify, `GET /health`, `GET /me`, optional `app_users`, `GET /data/status`,
`GET /accounts`, `GET /accounts/{account_id}`, `GET /dashboard` stub.  
Frontend: Vite, Tailwind tokens, Inter, router, Clerk login, shell, fictional badge, typed client.

Manual validation:

- [x] Health public; `/me` 401 without token; role `SALES_REP` with token.
- [x] Accounts list reads from `crm_master` only; fictional badge visible.
- [x] No new CRM tables created. (`app_users` + existing `crm_master` only.)

### Phase 2 — F2 Risk prioritizer (M) — can parallel with F1 after Phase 1 stubs

Follow `docs/features/F2_REVENUE_RISK_PRIORITIZER.md`.  
Backend: risk list/detail (`preset=needs_attention_today`); rule score read + **recompute**;
factors + evidence; action-log preview/confirm (recompute after confirm).  
Frontend: Risk list (Needs attention today chip), detail, band pills, Recompute control.  
Platform: dashboard briefing `href` → `/risk/:accountId`.

Manual validation:

- [ ] High-risk open/stalled deals sort correctly; reasons show stored evidence.
- [ ] Needs attention today = high **or** overdue follow-up.
- [ ] Recompute (manual + after action confirm) updates score/band; AI does not set the number.
- [ ] Briefing deep link opens `/risk/:id`.
- [ ] At-risk value note shown; not labelled lost revenue.
- [ ] No model required for list/score.

### Phase 3 — F1 Lost lead recovery (M)

Follow `docs/features/F1_LOST_LEAD_RECOVERY.md` (incl. §14 sample drafts, §15 Gmail fixtures).  
Backend: `/recovery`, detail, re-engagement draft, **Gmail OAuth + sync/thread**, CRM log
preview/confirm, reopen.  
Frontend: list + detail + draft approve + **New/Previous Gmail panel** + CRM log modal.

Manual validation:

- [ ] `ACC-0178` / `ACC-0180` / `ACC-0189` appear with PUBLIC_VERIFIED signal URL.
- [ ] Draft from generate or §14 samples; approve ≠ send.
- [ ] Sync Gmail (live or fixtures) shows New vs Previous as separate rows with sources.
- [ ] CRM log confirm updates activity only; reopen never automatic.

### Phase 4 — AI explanations glue (S/M)

Shared explanation endpoint or embed in F1/F2 detail: fact / interpretation /
recommended_action + evidence chips. Grounding guards from `AI_RAG_DESIGN.md` (trim to
`crm_master` ids).

Manual validation:

- [ ] No certainty language; no invented numbers; quotes substring-check against stored text.

### Phase 5 — F3 Meeting intelligence (L)

Backend: upload → storage → extract → save append `uploaded_meetings`. STT should-have.  
Frontend: upload UI, match confirm, extraction review, save.

Manual validation:

- [ ] Upload ACC-0181 txt; match account; save appends array; pre-generated meeting_* intact.
- [ ] Held-back: no invented approved budget/discount.
- [ ] Unsupported type rejected (`UNSUPPORTED_notes.csv` optional).
- [ ] Audio path (should-have) or clearly cut.

### Phase 6 — F4 Blocker resolution (L)

Backend: chunk/embed KB files into non-CRM `kb_chunks` (or equivalent); answer endpoint with
citations; approve/reject. Optional salesperson doc upload.  
Frontend: blocker Q&A, citation cards, insufficient-evidence state.

Manual validation:

- [ ] Brightspace / grade-sync questions → answered from OFF docs.
- [ ] Hosting / SOC2-style questions → partially_answered.
- [ ] Discount / SLA → insufficient_evidence.
- [ ] Citations verbatim from stored chunks; approve does not send.

### Phase 7 — F5 Drafts (M)

Follow `docs/features/F5_FOLLOWUP_PROPOSAL.md`.  
Backend: follow-up + proposal generate/patch/approve; completeness rules.  
Frontend: `/accounts/:id/drafts` tabs + ApprovalBar + amber completeness rail.

Manual validation:

- [ ] Uses requirements + `product_reference` only; open questions listed.
- [ ] Approve ≠ send; `deal_status` unchanged.
- [ ] ACC-0181 generate path; no invented prices/capabilities.

### Phase 8 — F6 Handoff (M)

Follow `docs/features/F6_CUSTOMER_HANDOFF.md`.  
Backend: mark-won (confirm), handoff get/generate/approve.  
Frontend: confirm dialogs, handoff view/checklist.

Manual validation:

- [ ] Handoff on non-won → `DEAL_NOT_WON`.
- [ ] Won pack shows requirements, stakeholders, risks, checklist.
- [ ] Mark won is explicit user action only (confirm checkbox).
- [ ] Proposal approve alone does not set won.

### Phase 9 — Demo polish (S)

Wire nav to all features; briefing dashboard; empty/loading/error states; accessibility pass on
demo path; rehearsal.

### Phase 10 — Stretch (nice)

Live signal refresh; HubSpot; charts; export. Only after must-haves pass.

### Phase 11 — F7 Signal Scout (stretch)

Follow `docs/features/F7_SIGNAL_SCOUT.md` only if F1–F6 happy paths are demo-ready.  
CRM search + Add target → Scan now → signals → potential opportunities (clean-room; no SIS code
copy).

Manual validation:

- [ ] Target card shows name, URL, last scanned, Scan now.
- [ ] Scan poll completes; evidence citations real or honest failure/fixture label.
- [ ] Opportunities labelled potential; score is rules-based.

---

## 5. Compressed path (if behind)

1. Phase 1 shell + accounts  
2. F2 list + F1 list with heroes  
3. F3 upload/save on ACC-0181  
4. F4 one answered + one insufficient question  
5. F5 one proposal draft approve  
6. F6 mark won + handoff on an existing won row (or one demo mark-won)

**Never cut:** evidence/citations, rule scores, human approval, `insufficient_evidence`, fictional
label, single-table CRM rule.

**Cut first:** HubSpot, live signal refresh, audio/STT, salesperson PDF upload, charts, pilot
metrics page, draft revisions history.

---

## 6. Must / should / nice

| Level | Items |
|---|---|
| Must | Auth, accounts, dashboard briefing, F1–F6 happy paths above, KB embed, approval gates |
| Should | STT audio, salesperson KB upload, charts, polish completeness panel |
| Nice | Live signal refresh, HubSpot, export |

---

## 7. Demo script (≈8–10 minutes)

1. Sign in → dashboard briefing (fictional badge).  
2. **F1:** Open ASU `ACC-0178` — lost reason + verified public signal + draft check-in → approve
   (show not sent).  
3. **F2:** High-risk stalled deal — score, factors, recommended action.  
4. **F3:** Upload Georgia Tech sample transcript → confirm ACC-0181 → review extraction → save.  
5. **F4:** Ask Canvas grade sync / Brightspace → cited answer; ask discount → insufficient.  
6. **F5:** Generate follow-up/proposal from meeting context → approve.  
7. **F6:** Open a won account handoff (or mark-won on a prepared open deal) → checklist.  
8. Close: at-risk ≠ lost; reopened ≠ recovered; human stays in control.

Fallback if AI down: F1/F2 rule lists + pre-seeded drafts + KB file open offline still show the
story; say model unavailable and continue.

---

## 8. Rehearsal checklist

- [ ] Cold start: env, DB count 200, FE/BE up  
- [ ] Demo script twice timed  
- [ ] Failure paths: 401, unsupported file, AI timeout notice  
- [ ] No secrets in repo or screenshots  

---

## Open questions

1. Final team size and feature assignment.  
2. Event rules on pre-written code.  
3. Whether `AI_RAG_DESIGN.md` / `UI_UX_DESIGN.md` get a light pass the same day (recommended).  

---

## Document history

| Date | Change |
|---|---|
| 2026-11-04 | Replaced import/multi-table plan with preloaded `crm_master` + parallel feature plan |
