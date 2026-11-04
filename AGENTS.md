# AI Revenue Recovery & Deal Intelligence Agent — Lumora Learning

Authoritative orientation document for every human and AI agent working in this repository.
Read this before writing any code, document, or plan.

**Current project stage: DOCUMENTATION ALIGNED TO PRELOADED MVP DATA (2026-11-04).**
Core docs (`DATABASE_DESIGN`, `DATA_SOURCES`, `API_CONTRACT`, `IMPLEMENTATION_PLAN`,
`TECHNICAL_PRD`, `UI_UX_DESIGN`, `AI_RAG_DESIGN`) describe the live `crm_master` dataset.
No application code until a phase in `IMPLEMENTATION_PLAN.md` is explicitly requested.
Do not invent requirements, data, endpoints, or schema.
Do not create test files unless explicitly requested.

**Independent repository.** This is its own hackathon project with its own git repository. It
reuses the technology stack, color theme, authentication pattern, and LLM provider of the
Excelsoft AI Sales Intelligence System, but it does not depend on that project's code,
documents, rules, or phases, and it must never edit that project. The only shared
infrastructure is the Supabase project (isolated by a separate schema, see
`docs/TECHNICAL_PRD.md`) and the Clerk application (to be confirmed).

---

## 1. What we are building

An AI sales agent for a B2B education-technology seller, the fictional company
**Lumora Learning**, which sells learning platforms, assessment tools, and analytics to
universities, colleges, K-12 districts, and enterprises.

Six AI capabilities form **one connected workflow**, not six separate apps:

| ID | Feature | One-line purpose |
|---|---|---|
| F1 | Lost Lead Recovery | Find inactive or lost deals worth reopening, explain why, draft a re-engagement |
| F2 | Revenue Risk Prioritizer | Rank open deals by urgency and risk, show the evidence, recommend an action |
| F3 | Meeting Intelligence | Turn a transcript or notes into structured requirements, blockers, and next steps |
| F4 | Deal Blocker Resolution | Answer a customer question from approved documents, with citations |
| F5 | Follow-up & Proposal Generator | Draft a tailored follow-up or proposal outline for human approval |
| F6 | Customer Handoff | When a deal is won, generate a structured handoff for delivery |

### What this product is NOT

It does not send email. It does not change a CRM. It does not mark a deal recovered or won
because a draft was generated. It does not claim a deal is lost or will close. It surfaces
evidence-backed recommendations and prepares work for a human to approve.

### The three-way distinction (non-negotiable)

Every insight must separate:

| Layer | Meaning |
|---|---|
| `fact` | What a stored record, transcript, or approved document actually says, with a citation |
| `interpretation` | What the system infers from those facts |
| `recommended_action` | What the salesperson should consider doing next |

A drafted email, proposal outline, or handoff is a **draft** owned by the human, not a fact.
Presenting an interpretation as a fact is a product defect.

---

## 2. User

One role: the **Sales Representative** (`SALES_REP`). A single signed-in salesperson sees every
company, deal, meeting, document, and draft. There is no manager role, no role metadata, and no
per-user row filtering in the MVP.

## 3. Data strategy

The CRM data (deals, activities, contacts, customer history, meetings, documents, catalogue) is
**synthetic and fictional**. There is no real customer relationship implied. Every such
record, document, email, and UI screen carries the label
**"Fictional demo data"**. CRM data is preloaded in Supabase table
`revenue_recovery.crm_master` (see `docs/DATABASE_DESIGN.md`). Knowledge-base markdown and sample
meeting files live under `backend/data/crm_master/`. The app reads CRM only from its own tables. A
live CRM connector is out of the MVP (optional stretch only, see `docs/PRODUCT_PRD.md`).

**Public-source layer (hybrid).** Real institutions appear as illustrative targets. Deals and
contacts remain fictional ("Illustrative CRM record…"). Where `signal_classification =
PUBLIC_VERIFIED`, the row carries a real official URL and a verified snippet (see loaded
`crm_master` and `docs/DATA_SOURCES.md`). No open web search. Live refresh is optional should-have.

The demo "today" is the fixed date on each row (`as_of_date` / `DEMO_AS_OF_DATE = 2026-11-04` for
the loaded dataset), so inactivity and close-date calculations never drift.

## 4. AI strategy

The AI layer is provider-configurable behind an adapter. The configured provider is
**Azure OpenAI**. Embeddings use `text-embedding-ada-002` at 1536 dimensions (to be verified at
implementation, see `docs/TECHNICAL_PRD.md` open questions).

**Rules compute the number; the model explains it.** Recovery priority and risk scores are
0–100 values calculated by deterministic code. The LLM never decides a score. It extracts,
retrieves, drafts, and explains stored values.

The model never invents: a company, deal, value, date, contact, product feature, price,
contract term, commitment, or source. Evidence identifiers and snippets are validated by the
backend. If evidence is insufficient the system says so and does not call the model to fill the
gap.

## 5. Evidence

Every flag, extraction, answer, and draft claim carries evidence: source type, stored record or
document id, title, date or `unavailable`, verbatim snippet, and relationship to the claim. The
model does not supply ids, URLs, or snippets that the backend did not give it. A URL exists only
for a public source the backend fetched. An insight with no
evidence is not stored and not shown.

## 6. Technology

| Layer | Choice |
|---|---|
| Frontend | React, Vite, Tailwind CSS, Zustand, TanStack Query, Recharts, `lucide-react`, React Router, Clerk React SDK, `@fontsource/inter` |
| Backend | Python, FastAPI, SQLAlchemy (async), Alembic, PyJWT (Clerk token verification only), httpx, beautifulsoup4 (public-page parsing only) |
| Database | Supabase PostgreSQL (shared project, **separate schema** `revenue_recovery`), pgvector |
| AI / RAG | Azure OpenAI chat model, `text-embedding-ada-002` embeddings, simple text splitter (LangChain splitter only if it installs cleanly) |
| Speech to text | Groq Whisper (free plan) behind an STT adapter, audio upload only, should-have. Audio is not stored |
| Auth | Clerk for identity. FastAPI verifies the bearer token. One role. Not Supabase Auth |
| Scheduling | None in the MVP. APScheduler is not used |
| Deployment | Localhost only: frontend on 5173, backend on 8000 (same ports as the closed parent Sales Intelligence app). Supabase is the only hosted component |

No Redis, Celery, Kafka, queues, caches, or microservices. One backend process.
No component library, CSS-in-JS, second state library, or second data-fetching library.
Do not add a dependency that `docs/TECHNICAL_PRD.md` does not name.

## 7. Vocabulary (use these names exactly)

| Term | Names |
|---|---|
| Role code | `SALES_REP` |
| Feature keys | `lead_recovery`, `risk_prioritizer`, `meeting_intelligence`, `blocker_resolution`, `proposal_generator`, `handoff`, `signal_scout` (F7 stretch) |
| Deal status | `open`, `won`, `lost`, `postponed` |
| Deal stage | `prospecting`, `discovery`, `proposal`, `security_review`, `negotiation`, `closed` |
| Priority / risk band | `high`, `medium`, `low` |
| Content layer | `fact`, `interpretation`, `recommended_action` |
| Draft type | `reengagement_email`, `followup_email`, `proposal_outline`, `handoff` |
| Draft state | `draft`, `approved`, `rejected` |
| Extraction field status | `confirmed`, `unconfirmed`, `unknown` |
| Answer status | `answered`, `partially_answered`, `insufficient_evidence` |
| Evidence source type | `crm_deal`, `activity`, `company_signal`, `transcript`, `kb_chunk` |
| Data origin | `synthetic` (CRM data), `public_web` (real institution and its fetched signals), `hubspot` (optional stretch import only) |
| Collection mode | `live`, `snapshot` |
| Meeting source | `sample`, `upload`, `audio` (text from speech-to-text) |
| Source page type | `newsroom`, `board_minutes`, `announcements`, `leadership`, `budget` |
| Source fetch status | `ok`, `failed`, `skipped_robots`, `never` |
| Organization type | `university`, `college`, `k12_district`, `enterprise` |
| Activity type | `email`, `call`, `meeting`, `proposal_sent`, `note`, `meeting_cancelled` |
| Activity direction | `inbound`, `outbound`, `internal` |
| Signal type | `budget_approved`, `funding`, `new_initiative`, `leadership_change`, `competitor_adoption` |
| Loss reason category | `budget`, `timing`, `leadership`, `competitor`, `price`, `other` |
| Score type | `recovery`, `risk` |
| Extraction category | `requirement`, `integration_need`, `budget_timing`, `decision_maker`, `blocker`, `deadline`, `next_step` |
| Evidence relationship | `supports`, `context` |

Say "may be worth reviewing", "recommended action", and "at risk". Never say a deal "will close",
"is lost", "is recovered", or "is guaranteed".

## 8. Guardrails

- A human approves every external message, proposal, and handoff. The system does not send.
- **At-risk value is not lost revenue. Reopened is not recovered.** Do not combine them.
- Do not mark a deal `won` or recovered because a draft exists. Marking won is an explicit user
  action.
- Do not invent product features, prices, contract terms, commitments, or customer signals.
- If the knowledge base does not cover a question, answer status is `insufficient_evidence`.
- Real institutions are illustrative targets. Never state or imply that a real institution is a
  customer, has a deal, or said or did anything the stored public snippet does not say.
- Collect only from the verified pages in `institution_sources`. No open web search, no crawling, no
  user-supplied URLs, no login-protected or JavaScript-only pages. Skip a page that `robots.txt`
  disallows. Never invent a signal when a fetch fails.
- Unverified facts stay marked `NEEDS VERIFICATION`.
- Do not claim the project is unique or guaranteed to win.

## 9. Documentation map

| Document | Responsibility |
|---|---|
| `docs/PRODUCT_PRD.md` | Problem, user, six features, workflow, MVP scope, success criteria |
| `docs/TECHNICAL_PRD.md` | Architecture, layering, pipelines, configuration, security, deployment |
| `docs/DATA_SOURCES.md` | Synthetic datasets, files, fields, volumes, scenarios, import (batch 2) |
| `docs/DATABASE_DESIGN.md` | Single table `crm_master`, JSONB shapes, indexes, KB vector note |
| `docs/AUTHENTICATION.md` | Clerk sign-in, token verification, single role |
| `docs/API_CONTRACT.md` | Endpoints on `account_id`, errors, enums |
| `docs/AI_RAG_DESIGN.md` | Extraction, retrieval, grounding, scoring, explanation |
| `docs/UI_UX_DESIGN.md` | Premium Hybrid colors (all features), screens, components |
| `docs/IMPLEMENTATION_PLAN.md` | Parallel feature build, validation, demo script |

Scoped guidance: `frontend/AGENTS.md`, `backend/AGENTS.md`.

## 10. Documentation authority

Order: this file, then `docs/PRODUCT_PRD.md`, `docs/TECHNICAL_PRD.md`, `docs/DATA_SOURCES.md`,
`docs/DATABASE_DESIGN.md`, `docs/AUTHENTICATION.md`, `docs/API_CONTRACT.md`,
`docs/AI_RAG_DESIGN.md`, `docs/UI_UX_DESIGN.md`, `docs/IMPLEMENTATION_PLAN.md`, then code.
When code and a document disagree, the document wins.

Conflict protocol: name the document and statement, say why it matters, propose the smallest
change, wait for approval before editing the source document, then update downstream documents.

## 11. Working agreement for AI agents

- Implement only the phase that `docs/IMPLEMENTATION_PLAN.md` names and the user requested.
  Validate it manually before the next.
- Must-have beats should-have beats nice-to-have. Do not cut evidence, the rules score, human
  approval, or the insufficient-evidence response.
- Keep changes inside the files the task needs.
- Use a feature branch. Do not commit directly to the shared branch.
- Do not commit `.env`, API keys, Clerk secrets, or Azure keys. Example files hold placeholders.
- When a requirement is ambiguous, ask. Do not guess a threshold, weight, URL, or endpoint.
