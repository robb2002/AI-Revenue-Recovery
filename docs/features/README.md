# Feature PRDs — parallel build guide

Each feature has its own PRD under this folder. **All feature owners must follow the same isolation
rules** so frontend and backend work can commit independently without merge conflicts.

## Shared documents (do not fork per feature)

| Document | Use for |
|---|---|
| `docs/UI_UX_DESIGN.md` | **Only** color system, shell, components, typography — Premium Hybrid for every feature |
| `docs/API_CONTRACT.md` | Paths and payloads; update the contract before inventing a field |
| `docs/DATABASE_DESIGN.md` | `crm_master` columns only — no new CRM tables |
| `docs/DATA_SOURCES.md` | Demo anchors and classifications |
| `docs/AI_RAG_DESIGN.md` | Grounding, scoring rules, forbidden inventions |
| `docs/AUTHENTICATION.md` | Clerk + `SALES_REP` |
| `docs/TECHNICAL_PRD.md` | Layering, ports, adapters |
| `docs/IMPLEMENTATION_PLAN.md` | Phases, cut order, demo script |

## Module isolation (mandatory)

| Layer | Own here | Do not touch (Platform / other features) |
|---|---|---|
| Frontend | `frontend/src/pages/fN_*/`, `frontend/src/features/fN_*/` | `app/` router shell (except registering your route), global tokens, shared `components/` unless Platform agrees |
| Backend routes | `backend/app/api/routes/fN_*.py` | Other `f*_*.py`, `core/auth.py` |
| Backend services | `backend/app/services/fN_*.py` | Other feature services |
| Shared | Call shared repository helpers for `crm_master` reads/writes | Do not add parallel CRM tables |

**Git:** branch `feat/f1-recovery`, `feat/f2-risk`, … One feature per PR. Rebase often. Never rewrite
another feature’s folder in the same commit.

**UI:** every feature must use semantic tokens from `UI_UX_DESIGN.md` §2. No per-feature palette.

## Feature index

| ID | PRD | Status |
|---|---|---|
| F1 | `F1_LOST_LEAD_RECOVERY.md` | Ready for implementation |
| F2 | `F2_REVENUE_RISK_PRIORITIZER.md` | Ready for implementation |
| F3 | `F3_MEETING_INTELLIGENCE.md` | Ready for implementation |
| F4 | `F4_BLOCKER_RESOLUTION.md` | Ready for implementation |
| F5 | `F5_FOLLOWUP_PROPOSAL.md` | Ready for implementation |
| F6 | `F6_CUSTOMER_HANDOFF.md` | Ready for implementation |
| F7 | `F7_SIGNAL_SCOUT.md` | Stretch — build after F1–F6 if time |
