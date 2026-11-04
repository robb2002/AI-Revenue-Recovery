# AI Revenue Recovery & Deal Intelligence Agent

Lumora Learning (fictional EdTech seller). One AI sales agent that monitors buying signals, recovers forgotten leads, ranks at-risk deals, turns meetings into CRM facts, answers blockers with citations, drafts the next move, and hands won deals to delivery. Humans approve every external step. Demo CRM data is fictional.

---

## Business problem

| Pain | What happens today |
| --- | --- |
| No signal monitoring | Public budget, leadership, and initiative news is not watched or linked to CRM |
| Forgotten leads | Lost / postponed deals sit idle even when the market reason may have changed |
| Silent pipeline risk | High-value open deals go quiet; reps notice too late |
| Meeting leakage | Requirements, blockers, and next steps stay in notes or recordings |
| Unanswered blockers | Security / LMS / pricing questions stall deals for days |
| Slow follow-ups | Tailored proposals take hours to assemble from scattered context |
| Broken handoff | Delivery inherits a thin CRM record; context dies at Closed Won |

Sales tools score CRM activity. They rarely watch public buying signals and connect them to recovery and outreach in one place.

---

## Our solution

Scout (F7) → Find (F1) → Assess (F2) → Understand (F3) → Resolve (F4) → Move forward (F5) → Preserve (F6)

| ID | Feature | What the rep gets |
| --- | --- | --- |
| F7 | Signal Scout | Watch curated public pages → cite buying signals → suggest potential opportunities |
| F1 | Lost Lead Recovery | Ranked inactive / lost deals, why to review (including signals), re-engagement draft |
| F2 | Revenue Risk Prioritizer | Open deals by urgency; factors + recommended action |
| F3 | Meeting Intelligence | Transcript / audio → requirements, blockers, next steps → confirmed CRM save |
| F4 | Deal Blocker Resolution | Question → KB answer with citations, or insufficient_evidence |
| F5 | Follow-up & Proposal Generator | Tailored draft for approve / reject |
| F6 | Customer Handoff | After win, structured delivery handoff |

Signals feed recovery: a verified public update can reopen the case for a forgotten lead. Scores stay rule-based; the LLM explains with evidence only. Drafts are never auto-sent.

---

## Business impact

| Outcome | How this drives it |
| --- | --- |
| Catch timing windows | Public signals watched and linked to accounts before competitors notice |
| Recover ignored pipeline | Lost / quiet deals ranked with reason + ready check-in |
| Protect forecast | Open risk ranked early with transparent factors |
| Shorten cycle time | Meeting extract + blocker RAG + draft in one flow |
| Raise trust | Citations + insufficient_evidence instead of hallucination |
| Preserve post-win value | Handoff carries requirements into delivery |

Pilot metrics (illustrative until a live baseline): inactive leads reviewed, response / meeting rate, opportunities reopened, high-risk deals actioned, blocker answer time, draft acceptance, handoff completeness.

Pitch line: at-risk value is not lost revenue; reopened is not recovered.

---

## Does this tool already exist?

Adjacent tools exist. This exact product shape does not.

| Category | Examples | What they cover | Gap vs us |
| --- | --- | --- | --- |
| CRM-native AI | Salesforce Einstein, HubSpot Breeze | Scoring, forecast, activity insights | Fragmented; weak recovery → handoff; often opaque scores |
| Conversation intelligence | Gong, Chorus / ZoomInfo | Call risk, coaching, deal boards | Strong on talk tracks; not full recovery + KB blocker + handoff |
| Revenue intelligence | Clari, Aviso, Outreach | Forecast, deal health, sequences | Enterprise-heavy; rarely one lightweight evidence agent |
| Generic AI assistants | ChatGPT / Copilot overlays | Draft text | No CRM evidence contract, no rule scores, invents facts easily |

---

## Extra features we give

| # | Extra | Why it matters |
| --- | --- | --- |
| 1 | One connected F1–F6 workflow (+ F7) | Not six disconnected demos |
| 2 | Rules score + AI explain | Auditable 0–100 bands; model cannot invent the number |
| 3 | Evidence contract | No citation → not shown |
| 4 | Fact / interpretation / action | Stops guesses looking like CRM truth |
| 5 | Human-in-the-loop CRM writes | Gmail match → preview → approve; drafts approve/reject only |
| 6 | Honest insufficiency | Blocker answers can refuse instead of inventing terms |
| 7 | Hybrid public signals | Real institution URLs + verified snippets, labelled illustrative |
| 8 | EdTech KB path | LMS / security questions from approved docs with citations |
| 9 | Meeting audio → text | Groq Whisper; audio not stored |
| 10 | Demo-safe posture | Fictional badge, fixed as_of_date, no silent email send |

---

## What is implemented

| Area | Status |
| --- | --- |
| Auth (Clerk), app shell, Briefing dashboard | Done |
| F1 Recovery list/detail, rule score, draft, CRM log | Done |
| Briefing Inbox (live Gmail → CRM match → approve) | Done |
| F2 Risk list/detail, recompute, factors, action log | Done |
| F3 Meetings sample / upload / extract / confirm save | Done |
| F3 Audio Whisper transcription | Done |
| F4 Blockers + Knowledge (RAG / citations) | Done |
| F5 Drafts (follow-up / proposal) | Done |
| F6 Handoff | Done |
| F7 Signal Scout | Done |
| Account switcher (meetings / drafts / blockers / handoff) | Done |
| Preloaded crm_master (~200 rows) + KB markdown | Done |

---

## Easy setup

Prerequisites: Node 20+, Python 3.11+, Supabase (schema revenue_recovery loaded), Clerk, Azure OpenAI. Optional: Google OAuth (Gmail readonly), Groq (audio).

| Step | Action |
| --- | --- |
| 1 | Clone repo |
| 2 | Copy backend/.env.example → backend/.env and fill keys |
| 3 | Copy frontend/.env.example → frontend/.env and fill keys |
| 4 | Backend: create venv, pip install -r requirements.txt, run uvicorn on 8000 |
| 5 | Frontend: npm install, npm run dev on 5173 |
| 6 | Open http://localhost:5173 and sign in with Clerk |

Backend env columns:

| Variable | Purpose |
| --- | --- |
| DATABASE_URL | Supabase Postgres (revenue_recovery) |
| CLERK_SECRET_KEY | Verify bearer tokens |
| AZURE_OPENAI_* / LLM_* / EMBEDDING_* | Chat + embeddings |
| GOOGLE_CLIENT_ID / GMAIL_LOGIN_HINT | Briefing Inbox (optional) |
| STT_API_KEY | Whisper audio (optional) |
| DEMO_AS_OF_DATE | Keep 2026-11-04 for demo math |

Frontend env columns:

| Variable | Purpose |
| --- | --- |
| VITE_CLERK_PUBLISHABLE_KEY | Sign-in |
| VITE_API_BASE_URL | http://localhost:8000 |
| VITE_GOOGLE_CLIENT_ID / VITE_GMAIL_LOGIN_HINT | Briefing Inbox (optional) |
| VITE_SIGNAL_SCOUT_FEATURE | true to show F7 |

Commands:

```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```
cd frontend
npm install
npm run dev
```

Health: GET http://localhost:8000/api/v1/health  
Clerk: allow origin http://localhost:5173  
Gmail: OAuth Web client, readonly scope, same client id in FE + GOOGLE_CLIENT_ID

---

## Demo script (8–10 min)

| Step | Show |
| --- | --- |
| 1 | Sign in → Briefing (fictional badge) |
| 2 | Optional: Inbox → Gmail refresh → preview → approve |
| 3 | F1 Recovery e.g. ACC-0178 → reason, signal, draft approve (not sent) |
| 4 | F2 Risk → score, factors, recommended action |
| 5 | F3 Meetings → ACC-0181 sample or audio → Extract → Save confirm |
| 6 | F4 → cited answer, then insufficient_evidence |
| 7 | F5 → generate draft → approve / reject |
| 8 | F6 → won account handoff |
| 9 | Close: at-risk ≠ lost; reopened ≠ recovered; human in control |

If AI is down: F1/F2 rule lists still tell the story.

---

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React, Vite, Tailwind, TanStack Query, Recharts, Clerk, React Router |
| Backend | Python, FastAPI, SQLAlchemy async, httpx |
| Database | Supabase PostgreSQL + pgvector (revenue_recovery) |
| AI | Azure OpenAI chat + text-embedding-ada-002 |
| STT | Groq Whisper (audio not stored) |
| Auth | Clerk, role SALES_REP |
| Run | UI 5173 / API 8000 |

---

## Docs map

| Doc | Use |
| --- | --- |
| AGENTS.md | Vocabulary, guardrails |
| docs/PRODUCT_PRD.md | Problem, features, MVP |
| docs/TECHNICAL_PRD.md | Architecture |
| docs/API_CONTRACT.md | Endpoints |
| docs/DATABASE_DESIGN.md | crm_master |
| docs/AI_RAG_DESIGN.md | Grounding and scoring |
| docs/IMPLEMENTATION_PLAN.md | Phases and checklist |
| docs/features/* | Per-feature PRDs |

---

## Guardrails

| Rule | Meaning |
| --- | --- |
| Fictional data | No real customer relationship implied |
| Human approve | System prepares; humans decide |
| No open crawl | Public signals only from verified pages |
| No invention | Model must not invent companies, prices, features, or commitments |
