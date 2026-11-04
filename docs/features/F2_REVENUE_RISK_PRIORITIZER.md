# Feature 2 PRD — Revenue Risk & Opportunity Prioritizer

**Status:** READY FOR EVENT IMPLEMENTATION  
**Feature key:** `risk_prioritizer`  
**Owner folders:** FE `frontend/src/pages/f2_risk/` (+ optional `features/f2_risk/`);  
BE `backend/app/api/routes/f2_risk.py`, `backend/app/services/f2_risk.py`  
(+ optional `backend/app/scoring/risk_score.py` if Platform keeps scoring shared — F2 may own a thin
wrapper that calls shared pure functions)  
**Branch:** `feat/f2-risk`

---

## 0. How to use this PRD

1. Read `docs/features/README.md` (parallel module rules — **mandatory**).  
2. Implement UI only with tokens/components from `docs/UI_UX_DESIGN.md` (Premium Hybrid — same as F1).  
3. Call F2 (+ shared account/dashboard) endpoints in `docs/API_CONTRACT.md` §5 and §7.  
4. Read/write only columns listed here from `revenue_recovery.crm_master`
   (`docs/DATABASE_DESIGN.md`).  
5. Scoring rules and explanation grounding: `docs/AI_RAG_DESIGN.md` §5.3 and §6.  
6. Demo anchors: `docs/DATA_SOURCES.md`.  
7. Do **not** generate automated test files unless explicitly asked.

This PRD is the full build brief for F2. F1 must not put risk-scoring UI in recovery modules; F2
must not implement recovery email-sync or reopen.

---

## 1. Goal (judge-facing)

Help a salesperson **see which open (and stalled) opportunities need attention first**, with a
**transparent 0–100 risk score**, **factor breakdown**, **evidence**, and a **recommended next
action**. Optionally log that action into CRM **only after human approval**. The system never
marks a deal lost or “will close,” and **at-risk pipeline value is never labelled lost revenue**.

**One-line pitch:** “We don’t hide the score — we show the evidence behind every high-risk deal.”

---

## 2. Parallel development contract (F2-specific)

| Area | F2 owns | Must not modify |
|---|---|---|
| Routes UI | `/risk`, `/risk/:accountId` | F1 `/recovery*`, F3–F6 routes; shell except nav registration |
| API | `/api/v1/risk`, `/accounts/{id}/risk`, risk-action preview/confirm | F1 email-sync, F3 meetings, F4 KB, F5 proposal, F6 mark-won |
| Services | Risk candidate filter, factor assembly, score read/recompute, explanation orchestration, optional action log apply | Recovery eligibility scoring (F1); KB retrieval (F4) |
| Shared | `crm_master` repository; optional shared `scoring/risk_score.py` | Do not create `scores` / `risk` tables for MVP |

**Commit hygiene:** only F2 folders (+ shared scoring file if agreed). No token/theme drive-bys.

---

## 3. User stories

1. As a sales rep, I see **open/stalled deals ranked by risk**, with band and value.  
2. As a sales rep, I open a deal and see **score + five (or mapped) factors**, each with evidence.  
3. As a sales rep, I read an AI **explanation** (fact / interpretation / recommended action) that
   cannot change the number.  
4. As a sales rep, I see **at-risk value** clearly labelled “not lost revenue.”  
5. As a sales rep, I can **preview logging the recommended action** to CRM and **approve** before
   any write.  
6. As a sales rep, a healthy low-risk deal is visible when filtered but does not dominate the
   default “needs attention” view.

---

## 4. Scope

### 4.1 In scope (MVP must)

- Risk list: `deal_status` in `open` | `stalled` (demo stalled = high urgency).  
- Default sort: `revenue_risk_score` descending, then `deal_value` descending.  
- Filters: band (`high` | `medium` | `low`), stage, optional min value.  
- Detail: `ScoreDisplay`, factor breakdown, evidence chips, blocker summary if present,
  inactivity / close date / follow-up overdue, layered AI explanation.  
- At-risk value strip on list (sum of **high** band open+stalled values) with honesty note.  
- Generate/refresh explanation (AI) with grounding; works offline on stored `risk_reason` if AI
  down.  
- **Log recommended action → CRM** with preview + confirm (mirrors F1 email-sync pattern, different
  fields).  
- **“Needs attention today” preset (must):** list filter =
  `risk_category = high` **OR** overdue follow-up
  (`next_followup_date` or `next_action_date` before `as_of_date`). Default list entry for judges may
  still be High band; preset is a first-class chip/toggle on `/risk`.  
- **Recompute score (must):** rules-only `POST .../risk/recompute`; also run automatically after
  successful **risk-action confirm** so CRM field changes refresh score/band. Detail page keeps an
  explicit **Recompute score** control.  
- **Dashboard deep link (must):** each briefing item that is risk-related links to
  `/risk/:accountId` (Platform wires `href` / router from `account_id` on `GET /dashboard`).  
- Fictional badge; IllustrativeBadge on real-institution names.  
- Loading / empty / error / AI-unavailable states.  
- Premium Hybrid colors: **high risk = red**, medium = amber, low = neutral; navy chrome; indigo
  only for AI Generate.

### 4.2 Out of scope (F2)

- Lost-lead recovery list, re-engagement email, reopen (F1).  
- Meeting upload (F3), blocker KB answers (F4), full proposal generator (F5), handoff (F6).  
- Auto-changing `deal_status` to lost/won.  
- Sending email.  
- New CRM tables.  
- Automated test suites.  
- Green-to-red heatmaps or unlabeled color scores.

### 4.3 Should-have (if time)

- Sparkline-free compact factor bars (navy fill) beyond the required factor list.  
- “Needs attention” count badge on sidebar Risk nav.

---

## 5. Data to use (`crm_master`)

### 5.1 List / filter fields

| Column | Use |
|---|---|
| `account_id`, `account_name` | Identity |
| `opportunity_id`, `opportunity_name` | Context |
| `deal_status` | Pool: `open`, `stalled` |
| `opportunity_stage` | Factor + filter |
| `deal_value`, `currency` | Value factor + sort |
| `revenue_risk_score` | Primary sort / display (0–100) |
| `risk_category` | Band: `high` \| `medium` \| `low` |
| `risk_reason` | Fallback explanation text |
| `recommended_next_action` | Action line |
| `inactivity_days`, `last_activity_date` | Inactivity factor |
| `expected_close_date`, `next_followup_date` | Close proximity / overdue |
| `blocker_detected`, `blocker_category`, `blocker_severity`, `blocker_status` | Risk signal / evidence |
| `is_decision_maker`, `contact_name` | Stakeholder risk context |
| `competitor_category`, `competitor_notes` | Competitor factor/context |
| `as_of_date` | Clock (`2026-11-04`) |
| `record_segment` | Optional filter (`stalled_at_risk`) |

### 5.2 Detail / evidence fields

| Column | Use |
|---|---|
| `activity_history`, `previous_interaction_summary` | Timeline evidence |
| `customer_objections`, `customer_requirements` | Context facts |
| `sales_engagement_count` | Engagement depth |
| `next_action`, `next_action_date` | Overdue next action |
| `signal_*` | Context only if relevant; do not invent |
| `product_interest`, `product_reference` | Display only |

### 5.3 Fields written by F2 (only after explicit human confirm on action log)

| Action | Columns updated |
|---|---|
| Explanation generate | Prefer **response-only** or optional cache fields if added later; do not invent columns mid-event. Showing `risk_reason` + AI panel in UI is enough for MVP |
| **Action log confirm** | Append `activity_history` (type `Note` or `Email` per choice); set `next_action`, `next_action_date` / `next_followup_date`; set `last_activity_date` / `activity_*` summary; optionally refresh `inactivity_days` from `as_of_date` |
| Score recompute | May update `revenue_risk_score`, `risk_category`, `risk_reason` **by rules only** |

**Never on F2:** `deal_status` → won/lost; clearing blockers as “resolved” without user intent;
F1 reopen; inventing competitor names.

### 5.4 Strong demo rows (use these)

Prefer **high** `risk_category` + `stalled` or long inactivity, e.g.:

| Pattern | Example accounts (verify in DB at event) |
|---|---|
| Stalled + high score + blocker | e.g. Seneca Polytechnic `ACC-0032`, University of Mumbai `ACC-0074`, HKU `ACC-0041` |
| Large value + overdue follow-up | Highest `deal_value` among high band |
| Low-risk contrast | An `open` + `low` row to show ranking is not random |

Spot-check with:

```sql
select account_id, account_name, deal_status, revenue_risk_score, risk_category, deal_value,
       inactivity_days, blocker_category
from revenue_recovery.crm_master
where deal_status in ('open','stalled') and risk_category = 'high'
order by revenue_risk_score desc nulls last
limit 10;
```

---

## 6. Backend design

### 6.1 Module layout

```
backend/app/
  api/routes/f2_risk.py
  services/f2_risk.py
  services/f2_action_log.py          # preview + confirm (can merge into f2_risk.py)
  scoring/risk_score.py              # pure functions (shared OK)
  repositories/crm_master.py         # shared
```

### 6.2 Responsibilities

| Service method | Behavior |
|---|---|
| `list_risk_accounts` | Filter open/stalled; support `preset=needs_attention_today`; sort by score/value; **no model** |
| `get_risk_detail` | Score, factors, evidence package, blocker snapshot, stored reason |
| `compute_risk_score` | Pure rules from `AI_RAG_DESIGN.md` §5.3 mapped to columns (§6.4) |
| `recompute_and_persist` | Write `revenue_risk_score` / `risk_category` / optional `risk_reason` |
| `explain_risk` | AI claims from supplied score+evidence only; cannot change score |
| `preview_action_log` | **No DB write.** Proposed activity + field updates |
| `confirm_action_log` | `confirm: true` → transactional CRM update **then recompute score** |
| `dashboard_at_risk_value` | Sum `deal_value` where band high and status open/stalled |
| `briefing_risk_links` | Dashboard briefing rows include `account_id` + `path: /risk/{id}` for risk items |

### 6.3 API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/risk` | Query: `band`, `deal_status`, `preset=needs_attention_today`, `sort=-revenue_risk_score`, pagination |
| GET | `/api/v1/accounts/{account_id}/risk` | Detail payload (§API_CONTRACT) |
| POST | `/api/v1/accounts/{account_id}/risk/explain` | Optional; returns claims + evidence |
| POST | `/api/v1/accounts/{account_id}/risk/recompute` | Rules only; updates score columns |
| GET | `/api/v1/accounts/{account_id}/risk-action/preview` | Preview CRM patch from recommended action |
| POST | `/api/v1/accounts/{account_id}/risk-action/confirm` | `{ "confirm": true }` applies patch |

List item should include: AccountSummary fields + `revenue_risk_score`, `risk_category`, top
factor label, `blocker_category` if open, `next_followup_date` overdue flag.

### 6.4 Scoring map (`crm_master` ↔ rules)

Use `as_of_date` on the row (dataset **2026-11-04**). Prefer **displaying stored**
`revenue_risk_score` / `risk_category` for speed; recompute must match bands used in UI.

| Rule concept | `crm_master` input |
|---|---|
| Eligibility | `deal_status` in `open`, `stalled` (treat stalled like open-at-risk for MVP) |
| Deal value | `deal_value` |
| Inactivity | `inactivity_days` or `as_of_date - last_activity_date` |
| Close proximity | `expected_close_date` vs `as_of_date` |
| Stage | Map `opportunity_stage` strings (e.g. Security & Procurement Review → security_review weight) |
| Overdue next action | `next_followup_date` or `next_action_date` < `as_of_date` |
| Blocker risk | open/`in_progress` blocker with `blocker_severity` high/medium → documented risk points |
| Missing decision maker | `is_decision_maker = false` → include in factors/evidence |
| Competitor | `competitor_category` not empty / not “None identified” |
| Bands | Align UI: high ≥ 60 or ≥ 70 — **match stored data**. If stored scores used thresholds
  high≥60 (seed generator), **UI bands must follow stored `risk_category`**, not a second
  conflicting cutoff. Document chosen rule in code constant `RISK_BAND_SOURCE=stored_category`
  for MVP demos. |

**Factor payload:** each factor has `key`, `label`, `points`, `max_points`, `detail`, and
`evidence_ids` pointing at deal/activity/blocker snippets assembled in code.

### 6.5 Action log — preview → approve → CRM (F2 equivalent of email sync)

Purpose: salesperson accepts the **recommended next action** as a CRM follow-up commitment.

```
recommended_next_action on row
  → User clicks "Log action to CRM"
  → GET risk-action/preview
       Builds proposed activity_history note + next_action / next_followup_date
  → Modal: will change / will not change
  → POST risk-action/confirm { confirm: true }
       Transactional update
  → UI refetch detail + list badges
```

**Preview must include `will_not_change`:**

- `deal_status` (still open/stalled)  
- `deal_value`  
- “At-risk value is not lost revenue”  
- No auto-mark lost / won  

**Proposed activity example:**

```json
{
  "date": "2026-11-04",
  "type": "Note",
  "direction": "internal",
  "description": "Risk follow-up committed: Resolve open procurement blocker…",
  "outcome": "Action logged by salesperson",
  "classification": "SYNTHETIC"
}
```

### 6.6 AI rules for F2

- Model explains **stored** score/factors only.  
- Must not invent inactivity days, values, or blockers.  
- Forbidden: will close, guaranteed, is lost (unless quoting a stored status fact carefully),
  recovered revenue.  
- AI down: show `risk_reason` + factors from rules; `AiUnavailableNotice` on Explain.

---

## 7. Frontend design

### 7.1 Module layout

```
frontend/src/pages/f2_risk/
  RiskListPage.tsx
  RiskDetailPage.tsx
frontend/src/features/f2_risk/
  components/RiskFactorList.tsx
  components/AtRiskValueBanner.tsx
  components/RiskActionApprovalModal.tsx
  hooks/useRisk.ts
  api.ts
```

Routes (Platform registers):

- `/risk` → list  
- `/risk/:accountId` → detail  

Nav: **Risk prioritizer** icon `ShieldAlert`.

### 7.2 Visual system (mandatory — same palette as F1)

| UI element | Token |
|---|---|
| Page background | `bg-app` (`neutral-50`) |
| Primary buttons | `navy-600` |
| Explain AI | `indigo-600` + `Sparkles` |
| High risk band | `red-600` / `red-50` |
| Medium risk band | `amber-600` / `amber-50` |
| Low risk band | `neutral-500` / sunken |
| At-risk banner | amber or navy surface + **text note**, never “lost” |
| Success after action log | `green-600` toast |
| AI panel | `surface-ai` / `surface-ai-subtle` |

### 7.3 List page `/risk`

**Header:** “Revenue risk prioritizer” + subtitle “What needs attention on open opportunities.”

**AtRiskValueBanner:**  
`At-risk pipeline: $X`  
Caption: **“At-risk value, not lost revenue.”**  
Do not add recovery value on this banner.

**Filters:** Preset chip **Needs attention today** (must); Band (default High when preset off);
Status (Open / Stalled / Both); Sort.

**Needs attention today:** shows high band **or** overdue `next_followup_date` /
`next_action_date` vs `as_of_date`. Overdue column highlighted amber.

**Table columns:** Account | Stage | Status | Value | Score | Band | Days inactive | Close date |
Blocker | Overdue follow-up | Open.

**Default view for judges:** Prefer preset **Needs attention today**, or Band = High, sort = score
desc — stalled high-value deals first.

**Row treatment:** high band filled red pill; selected row `navy-50`.

### 7.4 Detail page `/risk/:accountId`

**Summary card:** account, opportunity, value, stage, status, close date, inactivity, owner,
contact, decision-maker yes/no.

**Score block:** large `text-score`, `BandPill`, “out of 100”, `scoring_version` caption.

**FactorBreakdown:** bars navy-400 on sunken track; each row opens evidence.

**Blocker callout (if any):** category, severity, status — link text “Resolve with Blocker
workspace” → `/accounts/:id/blockers` (F4) if route exists; otherwise plain text for MVP.

**AiPanel explanation:** FACT / INTERPRETATION / RECOMMENDED ACTION + chips.

**CTA row:**

1. **Explain with AI** (indigo).  
2. **Log action to CRM** (navy primary) → preview modal.  
3. Secondary: **Recompute score** (ghost/secondary).  

**Timeline:** last 5 `activity_history` items.

**After action confirm:** toast; new timeline note; next follow-up date visible; **score/band
refreshed via automatic recompute** (and manual Recompute still available).

### 7.5 Risk action approval modal

Same UX pattern as F1 email sync:

- Title: **Review CRM updates before logging action**  
- Recommended action text  
- Field diff table  
- Will not change list (status, value, not lost revenue)  
- Cancel / Confirm  

### 7.6 States

| State | Behavior |
|---|---|
| Loading | Skeleton table / detail |
| Empty high filter | “No high-risk open deals. Try Medium or All.” |
| AI fail | Keep factors + `risk_reason` |
| Preview fail | Modal error; no write |
| Low-risk detail | Still full UI; calm bands |

---

## 8. End-to-end scenarios (must work in demo)

1. **Happy path high risk:** Open top high-risk stalled deal → show score 80+ → factors map to
   inactivity/blocker/close → AI explain → Log action → preview → confirm → timeline updates →
   score recomputed.  
2. **Needs attention today:** Preset includes a high deal and/or an overdue-follow-up deal.  
3. **Recompute:** Manual recompute changes displayed score/band from rules only (no AI).  
4. **Dashboard deep link:** From `/` briefing, click a risk item → lands on `/risk/:accountId`.  
5. **Ranking honesty:** Switch filter to Low — small active deals appear with low scores.  
6. **At-risk banner:** Matches sum of high-band values; caption visible.  
7. **AI down:** Factors still show; explain unavailable.  
8. **Preview without confirm:** DB unchanged.  
9. **No status corruption:** After action log, `deal_status` still open/stalled.  
10. **Cross-feature courtesy:** Blocker chip does not embed F4 retrieval inside F2 module.

---

## 9. Guardrails (non-negotiable)

- Rules own the number; model explains.  
- Human approval before CRM write from recommended action.  
- At-risk ≠ lost revenue; never combine with F1 recovery $.  
- No “will close” / “guaranteed” / confetti.  
- Same Premium Hybrid theme as F1–F6.  
- Single `crm_master` table only.  
- Fictional demo data label always on.

---

## 10. Acceptance criteria (manual)

1. `/risk` lists open+stalled with scores; high-band / needs-attention views are judge-ready.  
2. **Needs attention today** preset = high **OR** overdue follow-up vs `as_of_date`.  
3. Sort is score desc then value desc; reproducible for fixed `as_of_date`.  
4. Detail shows score, band, factors with evidence, blocker if present.  
5. At-risk banner includes honesty caption.  
6. Explain AI cannot change the number; **recompute** is rules-only and runs after action confirm.  
7. Action preview accurate; cancel writes nothing; confirm updates activity + next action fields.  
8. Dashboard briefing risk rows deep-link to `/risk/:accountId`.  
9. UI refetches after confirm/recompute.  
10. Colors: high=red, AI=indigo, chrome=navy.  
11. Code only in F2 modules (+ shared scoring if agreed).  
12. Copy compliant with product vocabulary.

---

## 11. Demo script snippet (F2, ~2 minutes)

1. From **Briefing** click a high-risk item → lands on `/risk/:id` (deep link).  
2. Or Nav → Risk → **Needs attention today** → point at **At-risk value, not lost revenue**.  
3. Open top high-risk row (stalled + blocker).  
4. Walk factors: inactivity, close date, blocker.  
5. Explain with AI — FACT vs RECOMMENDED ACTION.  
6. Log action → Confirm → timeline + **score recomputed**.  
7. Bridge: “Next we’d answer the blocker in Feature 4.”

---

## 12. Dependencies

| Need | From |
|---|---|
| Auth, shell, tokens, API client | Platform |
| Dashboard at-risk metric | May call F2 service or shared aggregate |
| F1 / F3 / F4 / F5 / F6 | Not required for F2 MVP |

---

## 13. Open questions

1. Band source after recompute: write both score and `risk_category` from the same rules constants;
   list may still show pre-seeded values until first recompute.  
2. Whether `stalled` uses identical formula as `open` (recommend: yes).  
3. Shared vs F2-owned `risk_score.py` — decide in Phase 1 with Platform.  
4. Overdue field precedence when both `next_followup_date` and `next_action_date` set — recommend:
   overdue if **either** is before `as_of_date`.

---

## Document history

| Date | Change |
|---|---|
| 2026-11-04 | Initial F2 feature PRD aligned to F1 structure + crm_master risk data |
| 2026-11-04 | Promoted to must-have: Needs attention today preset, recompute after CRM action, dashboard deep link to `/risk/:id` |
