# Technical PRD — AI Revenue Recovery & Deal Intelligence Agent

**Status:** APPROVED FOR MVP BUILD — aligned to preloaded `crm_master` (2026-11-04).  
**Supersedes:** CSV import service as the primary data path; multi-table CRM layout.

## Purpose of this document

This document defines the system architecture, layering, pipelines, configuration, security, and
deployment. It respects `AGENTS.md` and `docs/PRODUCT_PRD.md`. Tables, endpoints, AI prompts, and
screens are defined in `DATABASE_DESIGN.md`, `API_CONTRACT.md`, `AI_RAG_DESIGN.md`, and
`UI_UX_DESIGN.md`.

---

## 1. System architecture

```
Browser (React + Clerk)  — Premium Hybrid UI tokens (UI_UX_DESIGN.md)
   │  Authorization: Bearer <Clerk session token>
   ▼
FastAPI (one process)
   ├── Routes ─► Services ─► Repositories ─► Supabase PostgreSQL
   │              schema revenue_recovery.crm_master (+ optional kb_chunks, app_users)
   │                 │
   │                 ├─► AIService ─► Azure OpenAI (chat + embeddings)
   │                 └─► TranscriptionService ─► Groq Whisper (audio → text, should-have)
   ├── Knowledge indexer ─► backend/data/crm_master/knowledge_base/*.md ─► embeddings
   └── Signal collector (optional should-have) ─► curated official pages only
```

One backend process. No queue, cache, scheduler, or second service.  
**CRM data is already loaded** (200 rows). No sample CSV import in the MVP path.

## 2. Repository layout

```
AI_Revenue_Recovery_Agent/
  AGENTS.md
  docs/
  backend/
    AGENTS.md
    app/
      main.py
      core/            config, database, auth, errors, logging
      api/routes/      f1_recovery, f2_risk, f3_meetings, f4_blockers, f5_drafts, f6_handoff, …
      services/
      repositories/    crm_master SQL only for CRM
      ai/              AIService, retrieval, chunking, prompts
      scoring/         pure scoring functions
      collector/       optional public-page fetch (should-have)
      models/
      schemas/
    data/crm_master/
      schema.sql
      knowledge_base/  F4 markdown sources
      sample_meetings/ F3 demo uploads
    requirements.txt
    .env.example
  frontend/
    AGENTS.md
    src/
      app/             router, providers, shell
      pages/           f1_recovery, f2_risk, f3_meetings, f4_blockers, f5_drafts, f6_handoff
      components/      shared Premium Hybrid components
      api/
      stores/
      styles/          tokens from UI_UX_DESIGN.md (navy / indigo / amber / …)
    .env.example
```

Table and endpoint names are fixed by `DATABASE_DESIGN.md` and `API_CONTRACT.md`.  
UI colors are fixed by `UI_UX_DESIGN.md` §2 — every feature uses the same Tailwind tokens.

## 3. Frontend architecture

- **React + Vite + Tailwind.** Transcribe the **Premium Hybrid** palette exactly
  (`UI_UX_DESIGN.md` §2). Semantic tokens only in components — no per-feature color themes.
- **React Router** with routes in `UI_UX_DESIGN.md` §10. Guard → `/login`.
- **Clerk React SDK**; API client sends bearer token.
- **TanStack Query** for server data; **Zustand** for UI-only state.
- **Recharts** (should-have), **lucide-react**, **`@fontsource/inter`**.
- Long AI ops: one-request mutations with loading state (no polling).

Pages: Sign in, Briefing, Recovery, Risk, Account detail, Meetings, Blockers, Drafts, Handoff,
Knowledge (optional), Data status (read-only).

## 4. Backend architecture

### 4.1 Layering

```
Routes → Services → Repositories → PostgreSQL
Services → AIService → Provider adapter
```

| Layer | Responsibility | Must not |
|---|---|---|
| Routes | Parse, validate, authorize, call one service, shape the response | Hold business rules or SQL |
| Services | Business rules, orchestration, pipelines | Hold SQL |
| Repositories | All SQL and transactions | Hold business rules |
| Scoring | Pure functions: inputs in, score and factors out | Call a model or touch the database |
| AIService | Prompting, structured output validation, evidence validation | Know a vendor SDK |
| Adapter | One provider's chat and embedding calls | Hold business logic |
| TranscriptionService + STT adapter | Send one uploaded audio file to the speech-to-text provider and return text | Extract signals, score, or store evidence (the transcript then follows the normal extraction path) |

### 4.2 Services (plan)

`ImportService`, `DealService`, `LeadRecoveryService`, `RiskService`, `MeetingService`,
`TranscriptionService`, `KnowledgeService` (indexing and retrieval), `BlockerService`, `DraftService`, `HandoffService`,
`DashboardService`, `EvidenceService`, `ExplanationService`.

### 4.3 Request model

All endpoints are async. Operations that call the model run inside the request and return when
finished, with a configured timeout. There is no background job system in the MVP.

## 5. Database architecture

- **Supabase PostgreSQL** shared with another application. This project uses one dedicated schema,
  `revenue_recovery`.
- All tables, indexes, and the Alembic version table are created inside that schema. The database
  connection sets `search_path` to `revenue_recovery` for this application.
- No object in another schema is created, altered, dropped, or read. The one exception is
  resolving the `vector` type and its operators from the schema where the pgvector extension is
  installed (see `docs/DATABASE_DESIGN.md` §2). No application data outside `revenue_recovery` is
  accessed.
- **pgvector** stores embeddings for knowledge-base chunks and transcript chunks. The extension is
  enabled at database level already or enabled once by an approved migration step.
  `NEEDS VERIFICATION`: whether `vector` is installed and in which schema.
- Vector width is 1536 only after the embedding model is confirmed at implementation.
- Exact (not approximate) vector search is used. The data is a few hundred chunks.
- A "Reset demo data" action truncates and reloads only this schema's data tables.

Tables, columns, and constraints are defined in `docs/DATABASE_DESIGN.md`.

## 6. AI service architecture

```
Service → AIService → Provider adapter → Azure OpenAI
```

- **AIService** exposes task-level methods: extract meeting fields, answer a blocker, draft an
  email or outline, generate a handoff, explain a stored score. It builds the prompt, calls the
  adapter, parses structured output, validates evidence, and returns typed results.
- **Adapter** is the only code that knows Azure OpenAI. Switching provider changes the adapter and
  configuration, not services.
- **Configuration:** `LLM_PROVIDER=azure_openai`, `LLM_MODEL` (deployment name),
  `LLM_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, `LLM_TIMEOUT_SECONDS`.
  The parent project uses deployment `interns-gpt-4.1` and embedding `text-embedding-ada-002`.
  `NEEDS VERIFICATION`: that this project may use the same deployments and quota.
- **Structured output:** every task returns JSON validated by a Pydantic model. Invalid output is
  retried once, then returned as a controlled failure (no partial invented content).
- **Failure behavior:** a model timeout or error returns a clear error. The UI shows the stored
  data and a retry action. The model is never asked to fill a gap.

### 6.1 Grounding contract

The service gives the model candidate evidence items, each with an id. The model returns claims
that reference ids and quotes. The backend then:

1. rejects any id not supplied;
2. rejects any quote that is not a verbatim substring of the referenced source text;
3. drops claims left with no valid evidence;
4. stores only validated claims.

The model never supplies a URL, id, date, or number that did not come from the supplied data.

## 7. RAG architecture

```
Knowledge-base files / transcripts → clean → chunk → metadata → embeddings → pgvector
Question → embed → exact similarity search → similarity gate → top-k passages → LLM → grounded answer
```

- **Chunking:** about 1,200 characters with about 150 overlap, split on paragraph and sentence
  boundaries. Defaults mirror the parent project and are configuration, not constants.
- **Metadata:** document title, version, section, source type, fictional label.
- **Retrieval:** embed the question, rank by cosine similarity, apply the similarity gate
  (`EMBEDDING_SIMILARITY_GATE`, default taken from the parent project, `NEEDS VERIFICATION` on
  this corpus), return top-k.
- **No passage above the gate:** return `insufficient_evidence` and do not call the model.
- **Answer:** the model drafts only from the passages and returns the cited ids and quotes.
  Validation per §6.1. If part of the question has no supporting passage the status is
  `partially_answered`.
- Transcripts are chunked and embedded so extraction and later questions can cite them.
- CRM rows are structured data and are not embedded.

## 8. Data architecture (preloaded CRM)

```
Supabase revenue_recovery.crm_master  (200 rows, as_of_date 2026-11-04)
backend/data/crm_master/knowledge_base/*.md  →  index/embed at event  →  kb_chunks (non-CRM)
backend/data/crm_master/sample_meetings/*    →  F3 live upload demo files
Object storage (Supabase Storage)            →  uploaded meeting / salesperson docs
```

- Services **read and update** `crm_master` only for CRM. Do not add parallel CRM tables.
- Live meeting saves **append** `uploaded_meetings` after human confirm (see DATABASE_DESIGN).
- KB bodies are not stored in `crm_master`. Embeddings go to a vector table or equivalent.
- `GET /data/status` reports row counts; CSV import/reset is out of MVP unless re-approved.
- Classification labels (`PUBLIC_VERIFIED` / `SYNTHETIC` / `AI_GENERATED`) stay on the row /
  field groups. UI always shows "Fictional demo data".

## 8a. Public signal collection architecture (should-have)

```
institution_sources (reviewed list) → robots.txt check → fetch (httpx) → parse (BeautifulSoup)
 → clean text → signal extraction (model, closed types, verbatim quote) → validate
 → store company_signals with source_url, fetched_at, collection_mode
```

- **Source list.** Only URLs in `institution_sources`, loaded from the reviewed
  `institution_sources.json`. No URL comes from a request body, a model, or a page link.
- **Robots.** The collector reads each host's `robots.txt` with the standard library parser and the
  configured user agent. A disallowed page is recorded `skipped_robots` and not fetched.
- **Limits.** `SIGNALS_MAX_PAGES_PER_COMPANY`, `SIGNALS_MAX_PER_PAGE`, `HTTP_TIMEOUT_SECONDS`,
  and a delay of `SIGNALS_HOST_DELAY_SECONDS` between requests to one host. No JavaScript
  rendering, no login, no CAPTCHA handling, no crawling of links.
- **Extraction.** Cleaned page text (capped) goes to the model with the five closed signal types.
  The model returns signal type and a verbatim quote. The page date is parsed by code from the page
  text. If it cannot be parsed, `date_status` is `unavailable` and the signal is shown as context but
  ignored by scoring windows.
- **Storage.** The stored snippet is the matching span from the fetched text. The URL and fetch time
  come from the collector. Duplicates are skipped by `content_hash`.
- **Trigger.** `POST /signals/refresh` for one company at a time (so a request stays within the
  timeout). Import and reset never call the network. They load the committed snapshot
  (`public_signals_snapshot.json`) with `collection_mode = snapshot`.
- **Failure.** Every source ends with a status (`ok`, `failed`, `skipped_robots`). A failure
  creates no signal and does not affect other sources.
- **Dependencies.** `httpx` (already in the stack) and `beautifulsoup4`. No Playwright, no search
  API, no crawler framework.

## 9. Scoring architecture

- Two pure functions: recovery priority and deal risk. Each returns the 0–100 score, the band, and
  the factor contributions.
- Inputs: `crm_master` opportunity/activity/signal fields plus `as_of_date` / `DEMO_AS_OF_DATE`
  (`2026-11-04` for the loaded dataset).
- Weights and thresholds are configuration with a `scoring_version` (`v1`) in `AI_RAG_DESIGN.md`.
- The same inputs always give the same output.
- Scores live on the row (`revenue_risk_score`, `risk_category`, …) or are recomputed in code.
- The model receives the stored score and factors and writes the explanation. It cannot change them.

## 10. Pipelines

### 10.1 Lead recovery (F1)
```
Stored deals/activities/signals → candidate filter → recovery score → band
 → evidence assembly → explanation (model, grounded) → optional re-engagement draft
```

### 10.2 Risk prioritization (F2)
```
Open deals → risk score + 5 factors → band → evidence assembly → explanation (model) → ranking
```

### 10.3 Meeting intelligence (F3)
```
Upload file → object storage → text (or STT) → extraction (model) → snippet validation
 → rep confirms account_id → append uploaded_meetings (do not overwrite meeting_*)
```

### 10.4 Blocker resolution (F4)
```
Blocker/question → retrieval → gate → (answer via model | insufficient_evidence)
 → evidence validation → stored answer with citations
```

### 10.5 Proposal and follow-up (F5)
```
Confirmed requirements + product_reference + objections + answers → draft (model)
 → validation → completeness check → state `draft` → approve/reject (does not send)
```

### 10.6 Handoff (F6)
```
Rep marks deal won (explicit) → collect stored context → handoff (model, structured)
 → source validation → state `draft` → approve
```

## 11. Authentication architecture

- **Clerk** answers who the user is: sign-in, sign-out, session. The frontend never builds a login
  API.
- **FastAPI** verifies the Clerk session token (JWT, signature and expiry) with PyJWT, using the
  Clerk issuer keys. It does not issue JWTs.
- On a valid token FastAPI upserts a row in `revenue_recovery.app_users` keyed by the Clerk user id
  (email stored, no passwords, no secrets).
- **One role.** Every authenticated user is `SALES_REP`. There is no role metadata and no 403 role
  case. Missing or invalid token returns 401.
- `GET /api/v1/health` is the only public route.
- The mechanism is detailed in `docs/AUTHENTICATION.md`.

`NEEDS VERIFICATION`: whether to reuse the parent project's Clerk application. If shared, any user
who can sign in there can use this demo. This is acceptable for a hackathon and is recorded as a
known limitation.

## 12. API architecture

- Base path `/api/v1`. JSON. Bearer auth on every route except health.
- One error envelope for every failure (code, message, details, request id).
- Lists use pagination and documented filters.
- Enums use the names in `AGENTS.md` §7.
- Paths, shapes, and codes are fixed in `docs/API_CONTRACT.md`.

## 13. Error handling

| Case | Result |
|---|---|
| Missing/invalid token | 401, error envelope |
| Validation error | 422, error envelope |
| Not found | 404, error envelope |
| Model timeout/failure | 502 or 504 with a retryable code; stored data unaffected |
| Import row error | Reported in the import result; valid rows still load |
| Insufficient evidence | Not an error. A normal response with `insufficient_evidence` |

## 14. Logging

Structured logs with a request id. Log task name, duration, and outcome. Never log the Azure key,
Clerk secret, or full transcripts. Log prompt sizes, not prompt text.

## 15. Configuration and environment variables

Backend `.env.example` (placeholders only):

```
APP_ENV=local
LOG_LEVEL=INFO
DATABASE_URL=postgresql://postgres.<ref>:<password>@<pooler-host>:5432/postgres
DB_SCHEMA=revenue_recovery
CLERK_SECRET_KEY=sk_test_replace_me
CORS_ALLOWED_ORIGINS=http://localhost:5173
LLM_PROVIDER=azure_openai
LLM_API_KEY=replace_me
LLM_MODEL=replace_with_deployment_name
LLM_TIMEOUT_SECONDS=60
AZURE_OPENAI_ENDPOINT=https://YOUR_RESOURCE.openai.azure.com
AZURE_OPENAI_API_VERSION=replace_me
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_DIMENSIONS=1536
STT_PROVIDER=groq
STT_API_KEY=replace_me
STT_MODEL=replace_after_validation
STT_TIMEOUT_SECONDS=120
STT_MAX_AUDIO_MB=replace_after_validation
EMBEDDING_SIMILARITY_GATE=replace_after_validation
CHUNK_SIZE_CHARS=1200
CHUNK_OVERLAP_CHARS=150
RETRIEVAL_TOP_K=5
DEMO_AS_OF_DATE=YYYY-MM-DD
SCORING_VERSION=v1
HTTP_USER_AGENT=LumoraRevenueRecoveryDemo/0.1 (+local; research)
HTTP_TIMEOUT_SECONDS=15
SIGNALS_MAX_PAGES_PER_COMPANY=5
SIGNALS_MAX_PER_PAGE=5
SIGNALS_HOST_DELAY_SECONDS=1
```

Frontend `.env.example`:

```
VITE_API_BASE_URL=http://localhost:8000
VITE_CLERK_PUBLISHABLE_KEY=pk_test_replace_me
```

Local ports are **8000 (API)** and **5173 (web)** — same as the parent Sales Intelligence app,
which is closed so there is no port conflict. Do not copy real keys into any committed
file.

## 16. Security

- No secrets in git. `.env` is ignored.
- CORS allows only configured origins.
- Uploads: accept `.txt` and `.json` (decoded as text) and audio files (sent only to the speech-to-text
  provider), each with a size limit, never executed. Accepted audio formats and the size limit are
  confirmed in Phase 0 against the provider's documentation. Audio is not stored after
  transcription; only the resulting text is kept. The STT key is never logged.
- All user text sent to the model is treated as data. Prompts instruct the model to ignore
  instructions embedded in transcripts or documents. Output is validated, so injected text cannot
  create evidence.
- SQL through the ORM or bound parameters only.
- The schema isolation rule protects the other application's data.
- Data-status and mutating CRM actions are authenticated; they touch `revenue_recovery` only.
- **Fetch safety.** The collector fetches only URLs from the reviewed source list, only over HTTPS,
  with redirects limited to the same registered domain, a response size cap, and a content-type check
  for HTML. This prevents the refresh action being used to reach arbitrary or internal addresses.
- Page text sent to the model is treated as data; the prompt tells the model to ignore any
  instructions in it. Output cannot create a URL or evidence.

## 17. Performance and limits

- Data volume is small (about 30 deals, a few hundred chunks). Exact vector search is enough.
- Target response times: lists under 1 second; model tasks bounded by `LLM_TIMEOUT_SECONDS`.
- One uploaded transcript up to a few thousand words.
- Explanations are generated on demand and stored with the input values they explained,   so reopening
  a deal does not call the model again. Explanations for the hero deals are pre-generated during
  import; others are generated on first open.

## 18. Deployment architecture

- **Local only (decided):** backend on port **8000**, frontend on **5173**, both on localhost. Supabase is
  the only hosted component. The demo runs from the presenter's machine; there is no separate
  deployment target.
- Migrations run with Alembic against the isolated schema only.
- Environment variables are set in the host, not in code.

## 19. Team boundaries

| Area | Owner |
|---|---|
| `frontend/` shell + tokens | Platform / Frontend |
| Feature pages `pages/f*` | Feature owners (parallel) |
| API routes, services, repositories, scoring | Backend |
| `ai/`, KB embed, optional collector | AI and data |

Integrate through `API_CONTRACT.md`, `DATABASE_DESIGN.md`, and `UI_UX_DESIGN.md` (shared colors).

## 20. Architecture decisions summary

| Decision | Choice | Reason |
|---|---|---|
| Data source | Preloaded `crm_master` (200 rows) | Ready before coding; controlled demo |
| Database | Shared Supabase, schema `revenue_recovery`, single CRM table | Simple MVP, isolated from other apps |
| UI theme | Premium Hybrid tokens for all features | One production-looking product |
| LLM | Azure OpenAI behind an adapter | Same as parent, swappable |
| Scores | Pure rules, model explains | Trust and reproducibility |
| Evidence | Backend-validated ids and verbatim snippets | No fabricated citations |
| Retrieval | Exact pgvector over KB chunks + similarity gate | Small corpus |
| Auth | Clerk + FastAPI verification, one role | Same pattern, simplest |
| Jobs | Synchronous in-request | No queue needed |
| Scheduler | None | Nothing runs on a schedule |
| Public signals | Already on rows; live refresh optional | Real URLs where PUBLIC_VERIFIED |
| Speech to text | Groq Whisper (should-have) | Audio → same text path |
| Hosting | Localhost 8000 / 5173 | Hackathon demo (same as closed parent app) |

## 21. Component dependency map

```
Dashboard ─► DashboardService ─► crm_master aggregates
Recovery / Risk ─► scoring fields + ExplanationService ─► AIService
Meetings ─► MeetingService ─► storage + AIService ─► uploaded_meetings
Blockers ─► BlockerService ─► KnowledgeService ─► AIService
Drafts ─► DraftService ─► product_reference + meetings ─► AIService
Handoff ─► HandoffService ─► won-row context ─► AIService
All CRM services ─► Repositories ─► revenue_recovery.crm_master
```

## Open questions

0. Live public-signal refresh at event (should-have) vs snapshot-only on loaded rows.
1. ~~Clerk~~ **Decided: reuse parent Clerk application** (same limitation as before).
2. Confirm Azure OpenAI deployment names and quota.
3. Confirm `vector` extension schema; create `kb_chunks` at event if needed.
4. Confirm similarity gate on this KB corpus.
5. ~~Hosting~~ **Decided: localhost 8000 / 5173** (same as closed parent Sales Intelligence app).
6. Groq Whisper limits in Phase 0 (should-have audio).
7. Pre-seeded explanations vs on-demand generation for F1/F2 heroes (`ACC-0178`, etc.).
8. Is `search_path` + code discipline enough for schema isolation (hackathon OK)?
9. ~~F1 mailbox~~ **Decided (2026-11-04):** F1 uses **Gmail API readonly** for lead-matched
   threads (New vs Previous) plus CRM log-after-approve; sample drafts/fixtures in
   `docs/features/F1_LOST_LEAD_RECOVERY.md` §14–§15. **No auto-send.** Google OAuth client id/secret
   in env only; optional `gmail_connections` non-CRM table.
10. ~~F7 Pre-RFP~~ **Decided (2026-11-04):** Stretch feature **Signal Scout**
    (`docs/features/F7_SIGNAL_SCOUT.md`) — CRM or Add target → Scan now → signals → potential
    opportunities. Build after F1–F6; clean-room (do not copy AI Sales Intelligence System code).
