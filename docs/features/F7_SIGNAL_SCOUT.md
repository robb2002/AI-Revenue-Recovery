# Feature 7 PRD — Signal Scout (Pre-RFP signals & potential opportunities)

**Status:** READY FOR IMPLEMENTATION WHEN TIME ALLOWS (stretch after F1–F6)  
**Feature key:** `signal_scout`  
**Product name (UI):** **Signal Scout**  
**Owner folders:** FE `frontend/src/pages/f7_signal_scout/` (+ optional `features/f7_signal_scout/`);  
BE `backend/app/api/routes/f7_signal_scout.py`, `backend/app/services/f7_signal_scout.py`,  
`backend/app/services/f7_scan.py`, `backend/app/services/f7_opportunity.py`  
**Branch:** `feat/f7-signal-scout`

**Origin note:** Inspired by the business problem and thin workflow of the Excelsoft AI Sales
Intelligence System (detect → connect → potential opportunity). This hackathon feature is a
**clean-room slim slice** documented here — do **not** copy that project’s code, prompts, or
internal datasets. Rebuild against this PRD + this repo’s guardrails only.

---

## 0. How to use this PRD

1. Read `docs/features/README.md` (parallel module rules — **mandatory**).  
2. UI: `docs/UI_UX_DESIGN.md` only (Premium Hybrid — same as F1–F6).  
3. APIs: `docs/API_CONTRACT.md` §12 (Signal Scout).  
4. CRM reads: `docs/DATABASE_DESIGN.md` / `crm_master`. Public-source honesty: `docs/DATA_SOURCES.md`.  
5. Grounding / no invented evidence: `docs/AI_RAG_DESIGN.md` principles.  
6. Build **only after F1–F6 must-haves pass**, unless the team explicitly prioritizes stretch.  
7. Do **not** generate automated test files unless asked.

F7 must not implement F1 re-engagement/Gmail, F2 risk scoring, F3 meetings, F4 KB Q&A, F5 drafts, or
F6 mark-won. It may **deep-link** into `/recovery/:accountId` when a scanned CRM account is also a
recovery candidate.

---

## 1. Real sales problem (why this exists)

In B2B education sales, **waiting for a published RFP is often too late**: requirements are shaped,
incumbents are already talking, and the vendor list is effectively set.

The information that *precedes* formal procurement is usually **public but scattered** — board
budget votes, AI/learning initiatives, leadership changes, funding announcements, vendor
adoptions. A small sales team cannot continuously watch hundreds of institution sites, connect
related fragments, and decide which combinations deserve a call.

| Pain | Without Signal Scout | With Signal Scout |
|---|---|---|
| Scattered public updates | Manual bookmarking; coverage collapses when busy | On-demand **Scan now** for a chosen target |
| Single weak headline | Chase noise or ignore real clusters | Correlate related signals into a **potential** opportunity |
| “Why this account?” lives in someone’s head | Unauditable | Cited snippets + score factors |
| CRM vs net-new target | Either only known accounts or random browsing | **CRM search** or **Add target** (name + official URL) |

**What this is not:** a prediction that an RFP will happen, a guarantee of pipeline, or recovered
revenue. It surfaces **observable evidence** so a human can decide where to research next.

**One-line pitch:** “Find what changed at an institution before the RFP — with citations, not
hunches.”

---

## 2. Parallel development contract (F7-specific)

| Area | F7 owns | Must not modify |
|---|---|---|
| Routes UI | `/signal-scout`, `/signal-scout/:targetId` | F1–F6 page modules |
| API | `/signal-scout/*` (targets, search, scan, signals, opportunities) | Other feature routers |
| Services | Target resolve, scan orchestration, extract/validate, correlate, score, explain | Risk score, KB index, Gmail, handoff |
| Shared | Read `crm_master` for CRM targets; optional write-back of signal summary **only** with human confirm | No second full CRM deals product; no copy of SIS schema wholesale |

**Commit hygiene:** F7 folders only (+ Platform route registration + optional non-CRM tables
`signal_scout_targets`, `signal_scout_scans`, `signal_scout_signals`,
`signal_scout_opportunities` in schema `revenue_recovery`).

---

## 3. User stories

1. As a rep, I **search CRM** for an institution and open a **target card** (name, web URL, last
   scanned, Scan now).  
2. As a rep, I **Add target** when the institution is not in CRM (name + official website URL).  
3. As a rep, I click **Scan now** and see progress, then **signals** with evidence.  
4. As a rep, I see **potential opportunities** built only from correlated validated signals, with a
   rules score and AI explanation.  
5. As a rep, I never see “RFP will happen” or “guaranteed win.”  
6. As a rep, if a fetch fails or robots block a page, I see an honest failure — **no invented
   signal**.

---

## 4. Scope

### 4.1 In scope (F7 MVP must — when built)

- **Mode A — CRM target:** search `crm_master` by account name / id; card from stored
  `account_name`, website/URL fields if present, else institution official URL from
  `signal_source_url` domain / documented source list; `last_scanned_at` from F7 scan store.  
- **Mode B — Manual target:** name + HTTPS official URL; validate URL; store as scout target
  (`source=manual`).  
- **Target card:** name, web URL, last scanned (or Never), **Scan now**.  
- **Scan now:** async job (`202` + poll); **two-layer pipeline** (same shape as prior SIS
  event design, clean-room): fetch official `website_url` homepage → rank **same-domain**
  links → AI (or rules fallback) selects **page hubs** (§5.3a) → validate (https, same
  registrable domain/parent, robots, same-host redirects) → fetch → AI extract into the
  **seven signal types** (§5.3) with snippet-on-page check → correlate ≥2 → rules score
  (procurement relevance, related signal strength, EdTech relevance, recency, source
  reliability) → optional AI explain.  
- **Page hubs:** discovered live from the target homepage — **not** a hand-curated URL list.
  For `news` hubs, follow up to **3** same-domain article links after robots check.
  Cap: ≤8 hubs + ≤3 news children, **total ≤12 pages** per scan. No open web search.  
- **Signal extraction** into the **seven types** (closed taxonomy — see §5.3). Hubs ≠ types.  
- **Validation:** every signal needs at least one evidence item (URL, date or `unavailable`,
  verbatim snippet present on fetched page). Page failures never invent signals.  
- **Correlation → potential opportunity** when ≥2 related validated signals (or documented
  strong single procurement-type exception — **default: require ≥2** for hackathon honesty).  
- **Hybrid score 0–100** (rules); AI explains only.  
- **Results UI:** Signals tab + Opportunities tab; evidence drawer; `PublicSourceTag` /
  Illustrative CRM labels.  
- **Premium Hybrid:** amber = opportunity attention; indigo = AI explain; navy = Scan now;
  green = scan completed; red = scan failed (hard error only).  
- Discovered pages are **upserted into `signal_scout_pages`** keyed by university `target_id`
  (+ `account_id` when CRM-linked). No JSON fixture files.

### 4.2 Out of scope (do not build in F7)

- Full AI Sales Intelligence clone (Advisor chat, manager portfolio, competitor module).  
- **Scan All** / APScheduler continuous monitoring.  
- SAM.gov / USAspending as must-have connectors (nice stretch only).  
- Open web search / user arbitrary crawl of unrelated domains.  
- Auto-creating CRM `deal_status=open` rows without human confirm.  
- Claiming RFP certainty or recovered revenue.  
- Copying code or prompts from `AI_Sales_Intelligence_System`.  
- Automated test suites.

### 4.3 Should-have (if F7 time remains)

- “Save signal summary to CRM” preview → confirm (update `signal_*` on matching `account_id`
  only; never invent).  
- Deep link from opportunity → `/recovery/:accountId` when account is lost/inactive eligible.  
- Dashboard briefing chip: “Signal Scout: N new potential opportunities.”  
- Markdown export of opportunity evidence pack.

---

## 5. Data

### 5.1 Read from `crm_master` (Mode A)

| Column | Use |
|---|---|
| `account_id`, `account_name` | Search + card title |
| `organization_type`, `record_segment` | Context |
| Website / domain fields if present; else derive display URL from known institution sources | Card URL |
| Existing `signal_*`, `signal_classification`, `signal_source_url` | Show “already on file” vs new scan |
| `deal_status`, `recovery_eligibility` | Optional deep-link to F1 |
| `as_of_date`, `data_label` | Clock + fictional badge |
| `field_classification`, `institution_verification` | Honesty tags |

### 5.2 F7-owned storage (recommended non-CRM tables)

Keep deal CRM in `crm_master`. Persist scout runs separately (same pattern as `kb_chunks`):

| Table | Purpose |
|---|---|
| `signal_scout_targets` | `target_id`, `account_id` nullable, `name`, `website_url`, `source` (`crm`\|`manual`), `last_scanned_at` |
| `signal_scout_scans` | `scan_id`, `target_id`, `status` (`queued`\|`running`\|`completed`\|`failed`), stages, page outcomes, error summary, `started_at`, `finished_at`, `mode` (`live`) |
| `signal_scout_pages` | Discovered pages per university target: `url`, `page_category`, `status`, `account_id`, `scan_id` (unique `target_id`+`url`) |
| `signal_scout_signals` | signal rows + type, status, evidence jsonb, `scan_id` |
| `signal_scout_opportunities` | opportunity rows + score, factors, signal ids, explanation |

No per-account JSON fixture files. Pages live in `signal_scout_pages` after Scan now.

If event time is too short for migrations: keep last scan payload as jsonb on
`signal_scout_targets` only — document the tradeoff; prefer tables above.

### 5.3a Page hub categories (discovery — where we look)

Closed set of **nine** hub categories. These are **not** signal types.

| Hub category | Typical pages |
|---|---|
| `procurement` | Purchasing / RFP / bid boards |
| `technology` | IT / digital / modernization |
| `digital_learning` | LMS / online learning / teaching tech |
| `assessment` | Assessment / outcomes / testing |
| `funding` | Grants / budget / appropriations |
| `leadership` | Cabinet / CIO / leadership bios & news |
| `strategic_initiative` | Strategy / programs / initiatives |
| `partnership` | Industry / vendor / public–private partners |
| `news` | Newsroom hub **plus** limited same-domain linked articles |

**Mapping note:** a hub may yield zero or more signals of any of the seven types. Example: a
`news` article can be `technology_initiative` or `funding_budget`. `digital_learning` /
`assessment` hubs commonly feed `technology_initiative` or `strategic_announcement` — they do
**not** add eighth/ninth signal types.

### 5.3 Signal types (closed — what we store)

1. `procurement` — RFP / RFI / solicitation / buying notices  
2. `technology_initiative` — IT / digital / platform / modernization  
3. `leadership_change` — CIO / leadership / cabinet moves  
4. `funding_budget` — grants / budget / funding  
5. `strategic_announcement` — strategy / programs / initiatives  
6. `competitor_vendor` — vendor adoption / partnership / competitor activity  
7. `contract_renewal` — contract / renewal / agreement activity  

No eighth type at runtime.

### 5.3b Page validation (before fetch)

Every candidate URL must pass:

1. **HTTPS** only — reject shorteners and unrelated blogs.  
2. **Same registrable domain** as the target `website_url` (subdomains allowed, e.g.
   `news.asu.edu` under `asu.edu`).  
3. **Same parent host family** — news child links may not jump to third-party domains.  
4. **robots.txt** — disallowed → `skipped_robots`, no fetch, no signal.  
5. Caps as in §4.1.

`page_outcomes` item shape:

| Field | Values |
|---|---|
| `url` | Absolute HTTPS URL |
| `page_category` | One of the nine hubs in §5.3a |
| `status` | `ok` \| `failed` \| `skipped_robots` \| `domain_mismatch` |
| `title` | Human label or fetch note |

### 5.4 Demo targets

| Target | Mode | Why |
|---|---|---|
| `ACC-0178` ASU | CRM | Already has PUBLIC_VERIFIED signal — show “on file” + rescan |
| `ACC-0180` CSU | CRM | Same |
| `ACC-0189` Ohio State | CRM | Same |
| One manual URL | Add target | Prove non-CRM path (official .edu newsroom only) |

---

## 6. Backend design

### 6.1 Modules

```
api/routes/f7_signal_scout.py
services/f7_signal_scout.py    # targets, search, assemble card
services/f7_homepage_links.py  # same-domain link rank + category guess
services/f7_page_validate.py   # https, same-domain/parent, robots
services/f7_discovery.py       # homepage → AI/rules hubs → fetch + news articles
services/f7_signal_extract.py  # AI extract 7 types; snippet must be on page
services/f7_scan.py            # orchestrate live discovery; persist pages to DB
services/f7_opportunity.py     # correlate, rules score, explain
```

### 6.2 Pipeline

```
Select/Add target
  → POST scan (202 + scan_id)
  → resolve_hubs (fetch website_url → same-domain candidates → AI/rules pick hubs)
  → validate_pages (https, same domain/parent, robots, same-host redirect)
  → fetch (ok hubs + capped news articles)
  → extract (seven signal types; snippet on page)
  → validate_evidence
  → correlate (≥2) → rules score 0–100
       (procurement_relevance, related_signal_strength, assessment_edtech_relevance,
        recency, source_reliability)
  → optional AI explanation of score (never changes the number)
  → completed | failed
  → upsert signal_scout_pages for this university target
UI polls GET scan until terminal; page_outcomes + stored pages show hub coverage
```

### 6.3 API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/signal-scout/targets/search?q=` | CRM hits + recent manual targets |
| POST | `/api/v1/signal-scout/targets` | Body: `{ account_id }` **or** `{ name, website_url }` |
| GET | `/api/v1/signal-scout/targets/{target_id}` | Card payload |
| POST | `/api/v1/signal-scout/targets/{target_id}/scan` | Start scan → `202` + `scan_id` |
| GET | `/api/v1/signal-scout/scans/{scan_id}` | Status, progress, counts |
| GET | `/api/v1/signal-scout/targets/{target_id}/signals` | List |
| GET | `/api/v1/signal-scout/targets/{target_id}/opportunities` | List |
| GET | `/api/v1/signal-scout/opportunities/{opportunity_id}` | Detail + evidence |
| POST | `/api/v1/signal-scout/opportunities/{id}/explain` | AI explain score (optional) |

Errors: `422 INVALID_URL`, `409 SCAN_IN_PROGRESS`, `403 ROBOTS_BLOCKED` (per page, recorded on
scan), `502 FETCH_FAILED`, `404`.

### 6.4 Scoring (rules own the number)

Factors (document weights in one constant module): signal count/types diversity, freshness vs
`as_of_date`/scan time, procurement/funding presence, evidence quality (dated URL). AI never sets
the integer.

### 6.5 Guardrails in code

- Snippet must appear in fetched HTML/text.  
- No model-supplied URLs.  
- Forbidden UI/API phrases: will win RFP, guaranteed procurement, recovered revenue.  
- Manual targets: only `http(s)` official institution hosts — reject link shorteners / random blogs
  for MVP (allowlist pattern: prefer `.edu` / known institution domains from CRM).

---

## 7. Frontend design

### 7.1 Routes

- `/signal-scout` — search + add target + recent targets  
- `/signal-scout/:targetId` — card + Scan now + results  

Nav: **Signal Scout** icon `Radar` (or `ScanSearch`). Amber emphasis for opportunity attention.

### 7.2 Layout

**List / home**

1. Toggle or tabs: **From CRM** | **Add target**  
2. Search box → result rows → open target  
3. Add form: Name, Website URL, Create target  
4. Recent scans list  

**Target detail**

1. **Card:** name, URL (external), last scanned, CRM account chip if linked, Scan now (navy)  
2. Scan progress (poll)  
3. Tabs: **Signals** | **Potential opportunities**  
4. Opportunity detail: score, factors, linked signals, evidence chips, AI explain (indigo)  
5. Honesty banner: potential ≠ committed pipeline; public sources only  

### 7.3 States

Empty search, invalid URL, scan running, scan failed (show per-page outcomes), no signals found
(honest empty), AI explain unavailable (score still shows).

---

## 8. End-to-end scenarios

1. Search “Arizona State” → open ACC-0178 card → Scan now → signals + ≥1 potential opportunity
   **or** honest empty.  
2. Add manual target with official newsroom URL → scan → citations open in new tab.  
3. Second Scan now while running → `409 SCAN_IN_PROGRESS`.  
4. Robots-blocked page → recorded skipped; no fake signal.  
5. Opportunity copy never says RFP is certain.  
6. CRM-linked lost account shows optional “Review in Lead Recovery” link (no auto navigation).

---

## 9. Guardrails (non-negotiable)

- Human interprets; system does not claim deals or RFPs.  
- Evidence or no store.  
- No open crawl; robots honored.  
- Clean-room vs SIS codebase.  
- Fictional / illustrative labels on CRM-linked rows.  
- Same Premium Hybrid theme.  
- Single-role `SALES_REP`.

---

## 10. Acceptance criteria (manual)

1. CRM search and Add target both produce a usable card.  
2. Scan now returns pollable status and terminal completed/failed.  
3. Every displayed signal has evidence with snippet + URL when fetch succeeded.  
4. Opportunities are labelled **potential**; score has factors; AI does not invent the number.  
5. Failed/blocked pages do not invent signals.  
6. UI tokens match shared design system; code isolated under F7 modules.  
7. No SIS source files copied into this repo.

---

## 11. Demo script (~1.5–2 min) — only if F7 is built

1. Nav → **Signal Scout** — “Before the RFP, what’s publicly changing?”  
2. Search CRM hero → card → **Scan now**.  
3. Show one signal + citation.  
4. Open potential opportunity — score + why signals were connected.  
5. Bridge: “If they’re already in CRM as lost/inactive, F1 helps re-engage with the same honesty.”

---

## 12. Dependencies

| Need | From |
|---|---|
| Auth, shell, nav slot | Platform |
| `crm_master` search | Shared repo |
| httpx + robots checks | Backend stack (already named for public pages) |
| Azure OpenAI | Extract/explain (rules score offline-capable) |
| F1–F6 | Not required to *run* F7; build order prefers them first |

---

## 13. Open questions

1. Minimum signals to form an opportunity — **default ≥2** validated.  
2. Whether manual targets may use non-`.edu` enterprise domains in MVP.  
3. Persist scan tables vs jsonb-on-target for first cut.  
4. Optional SAM.gov connector — stretch only.

---

## Document history

| Date | Change |
|---|---|
| 2026-11-04 | Initial F7 Signal Scout PRD: real pre-RFP sales problem, CRM/Add target, Scan now, signals, potential opportunities; stretch after F1–F6; clean-room vs SIS |
| 2026-11-04 | Two-layer pipeline: 9 page hubs vs 7 signal types; same-domain/parent + robots validation; page_outcomes shape; scan stages |
| 2026-11-04 | Live discovery from website_url (homepage links + AI); SIS-shaped score factors |
| 2026-11-04 | Removed JSON fixtures; store discovered pages in `signal_scout_pages` per university target |
