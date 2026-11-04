# Data Sources — AI Revenue Recovery & Deal Intelligence Agent

**Status:** APPROVED FOR MVP BUILD — aligned to the loaded Supabase dataset (2026-11-04).  
**Supersedes:** the earlier CSV/JSON sample-pack plan under `backend/data/sample/`.  
**Database contract:** `docs/DATABASE_DESIGN.md` and `backend/data/crm_master/schema.sql`.

## Purpose of this document

This document describes **what data the MVP already has**, where it lives, how it is classified,
which demo anchors to use, and which files remain on disk for F3/F4. It does **not** define a
CSV import pipeline. Seeding scripts were removed after load.

---

## 1. Principles

1. **CRM is already in Postgres.** `revenue_recovery.crm_master` holds **200** rows. Do not invent
   a second CRM store.
2. **Label demo data.** UI must show **“Fictional demo data”**. Real institution names are
   illustrative targets, not customers.
3. **Classification.** Field groups use `PUBLIC_VERIFIED` | `SYNTHETIC` | `AI_GENERATED` (see
   `field_classification` on each row).
4. **Fixed clock.** All day math uses `as_of_date = 2026-11-04` on every row (not the wall clock).
5. **Evidence-ready.** Prefer stored ids, verbatim snippets, and real URLs already on the row or in
   KB files. The model must not invent ids, URLs, or snippets.
6. **No phone numbers.** `contact_phone` is null. Emails use `@example.com` patterns.

---

## 2. Fixed demo date

`DEMO_AS_OF_DATE = 2026-11-04` (stored as `crm_master.as_of_date`).

`docs/PRODUCT_PRD.md` / older drafts that say `2026-10-30` are superseded for this dataset.

---

## 3. Where data lives

| Location | What | Status |
|---|---|---|
| Supabase schema `revenue_recovery`, table `crm_master` | Full CRM / opportunity context for all six features | **Loaded (200 rows)** |
| `backend/data/crm_master/knowledge_base/*.md` | F4 approved documents (10 official excerpts + 11 synthetic) | **On disk; embed at event** |
| `backend/data/crm_master/sample_meetings/` | F3 live-upload demo transcript + audio | **On disk; not pre-inserted** |
| `backend/data/crm_master/schema.sql` | DDL reference | Keep |
| Object storage (Supabase Storage) | Uploaded meeting/KB binaries at runtime | **Create at event** |

There is no active `backend/data/sample/*.csv` pack for this MVP.

---

## 4. Dataset shape (loaded)

### 4.1 Grain

One row = one account context (lead and/or opportunity fields on the same row).  
Business key: `account_id` (e.g. `ACC-0181`). Opportunity key when present: `opportunity_id`.

### 4.2 Approximate segment mix (illustrative)

| `record_segment` | Role in demo |
|---|---|
| `early_lead` | Signal / early outreach |
| `qualified_lead` | Working lead |
| `active_opportunity` | Open pipeline |
| `stalled_at_risk` | F2 priority |
| `lost_inactive` | F1 recovery |
| `won` | F6 handoff |

`deal_status` values in the loaded data include: `open`, `won`, `lost`, `stalled`, `inactive`,
`none` (see `DATABASE_DESIGN.md` for mapping notes vs `AGENTS.md` vocabulary).

### 4.3 Feature coverage (already present)

| Feature | Data present |
|---|---|
| F1 | Lost/inactive pool; `lost_reason`; `recovery_eligibility`; follow-up drafts; **3 PUBLIC_VERIFIED recovery heroes** |
| F2 | Open/stalled rows with `revenue_risk_score`, `risk_category`, `risk_reason`, blockers, inactivity |
| F3 | ~140 rows with pre-generated `meeting_*` + extractions; `uploaded_meetings = []` everywhere |
| F4 | Blocker fields + `supporting_document_reference` pointing at KB ids |
| F5 | Follow-up drafts (all `draft`); proposal drafts on many opportunities |
| F6 | 25 won rows with full handoff JSONB packs |

Exact counts may drift only if the database is deliberately changed; treat Supabase as source of
truth at event start (`select count(*) …`).

---

## 5. Classification guide

| Kind | Label | Examples |
|---|---|---|
| Institution name + official website | `PUBLIC_VERIFIED` | Verified homepage identity |
| Public news/signal with real URL + verbatim snippet | `PUBLIC_VERIFIED` | ASU / CSU / Ohio State recovery signals |
| Contacts, deals, values, activities, meetings, blockers | `SYNTHETIC` | Illustrative CRM |
| Scores, explanations, draft email/proposal bodies, meeting insights | `AI_GENERATED` | Scripted or model; human approval required |
| Knowledge-base official excerpts | `PUBLIC_VERIFIED` excerpts + own-words summary | `KB-OFF-*` |
| Knowledge-base process templates | Illustrative / `SYNTHETIC` | `KB-PRC-01`, `KB-SEC-01`, … |

---

## 6. Public signals

- About **10** rows carry `signal_classification = PUBLIC_VERIFIED` with a real `signal_source_url`
  and a snippet that was checked against the page at collection time.
- Remaining signal rows may be `SYNTHETIC` and must not be presented as real announcements.
- **F1 heroes with verified signals (use these in the demo):**

| `account_id` | Institution | `deal_status` | Signal theme |
|---|---|---|---|
| `ACC-0178` | Arizona State University | lost | ASU News — agentic AI / learning platform |
| `ACC-0180` | California State University | lost | CSU / SDSU AI initiative |
| `ACC-0189` | The Ohio State University | inactive | AI Fluency initiative |

Do not invent new public URLs during the event unless a controlled collector is built and reviewed.

---

## 7. Knowledge base files (F4)

Path: `backend/data/crm_master/knowledge_base/`

| Prefix | Count | Use |
|---|---|---|
| `KB-OFF-01` … `KB-OFF-10` | 10 | Short official Pearson-page excerpts + citations |
| `KB-PRC-01`, `KB-PRD-02`, `KB-SEC-01`, `KB-INT-01`, `KB-PRO-01`, `KB-LGL-01`, `KB-BUD-01`, `KB-STK-01`, `KB-IMP-01` | 9 | Match CRM `supporting_document_reference` |
| `KB-SUP-01`, `KB-CMP-01` | 2 | Support / competitive handling (insufficient-evidence demos) |

Index and planted question intents: see `knowledge_base/README.md`.

**Event task:** chunk → embed → store in a non-CRM vector table (e.g. `kb_chunks`). Do not paste
full documents into `crm_master`.

**Optional stretch:** salesperson-uploaded PDF/DOCX → storage → same chunk store, labelled
`salesperson_upload`.

---

## 8. Sample meetings (F3 live upload)

Path: `backend/data/crm_master/sample_meetings/`

| File | Purpose |
|---|---|
| `ACC-0181_followup_call_2026-10-28.txt` | Primary transcript upload (names ACC-0181 / OPP-0181) |
| `ACC-0181_followup_call_2026-10-28.wav` | Optional STT path |
| `UNSUPPORTED_notes.csv` | Optional reject-format test |
| `README.md` | Target account + held-back fact |

**Held-back fact:** transcript does **not** approve a budget amount or discount. Extraction must
not invent those.

After salesperson confirm/approve, append one object to `uploaded_meetings`. Do not overwrite
pre-generated `meeting_*` columns.

---

## 9. Product claims

Product wording for proposals comes from `product_reference` jsonb on each row (official URL +
claim text) and optionally from `KB-OFF-09` / `KB-OFF-10`. There is no separate
`product_catalog.csv` in this MVP.

---

## 10. What not to load / not to claim

- Do not reintroduce multi-table CSV import as a must-have.
- Do not claim Pearson or any institution is a real customer of this demo seller.
- Do not store secrets in the database or in committed files.
- Do not treat at-risk open pipeline value as lost revenue, or reopened interest as recovered cash.

---

## 11. Validation checklist (manual, event start)

- [ ] `select count(*) from revenue_recovery.crm_master` = 200  
- [ ] `uploaded_meetings` exists and is `[]` on a spot check  
- [ ] F1 heroes `ACC-0178`, `ACC-0180`, `ACC-0189` are eligible + `PUBLIC_VERIFIED` + non-null URL  
- [ ] `ACC-0181` exists with open opportunity and sample files on disk  
- [ ] `knowledge_base/` contains the 21 markdown documents  
- [ ] No `.env` secrets committed  

---

## Open questions

1. Whether a live public-signal refresh runs at the event (should-have) or snapshot-only.
2. Supabase Storage bucket naming for uploads.
3. Whether `app_users` is created on first Clerk sign-in (see `AUTHENTICATION.md`).

---

## Document history

| Date | Change |
|---|---|
| 2026-11-04 | Replaced CSV sample-pack design with loaded `crm_master` + on-disk KB/meetings |
