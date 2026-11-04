# Frontend — Agent Guide

Read the root `AGENTS.md` first. This file does not override it.

**Implement only when a frontend task in `docs/IMPLEMENTATION_PLAN.md` is explicitly requested.**

## Documents you implement

| Document | What you take from it |
|---|---|
| `docs/UI_UX_DESIGN.md` | Tokens, components, layout, states, accessibility |
| `docs/API_CONTRACT.md` | Every path, field, enum, and error code |
| `docs/AUTHENTICATION.md` | Clerk sign-in, route guard, `GET /api/v1/me` |
| `docs/IMPLEMENTATION_PLAN.md` | Must / should / nice, and the phase checks |

## Stack

React, Vite, Tailwind CSS, Zustand, TanStack Query, Recharts, `lucide-react`, Clerk's React SDK,
React Router. Do not add a component library, CSS-in-JS, another data library, or another state
library.

## State

TanStack Query owns server data. Zustand owns filters, open panels, and unsaved draft edits. Do
not copy API data into Zustand.

## API

Call only paths in `docs/API_CONTRACT.md`. Send the Clerk session token as
`Authorization: Bearer`. If a screen needs a field the contract does not have, stop and update the
contract first. Do not invent a key. Do not hardcode a company, deal, score, or evidence snippet.

## UI rules

- Use semantic tokens from `UI_UX_DESIGN.md`. No raw hex in components. The color theme is the
  "Premium Hybrid" palette used by the Excelsoft project (navy structure, indigo for AI, amber for
  attention, green positive, red risk).
- Indigo means AI-generated. Amber means recoverable or attention. Red means at risk.
- A score component shows value, band, factors, and the explanation status.
- Every data view has loading, empty, error, and populated states. `insufficient_evidence` has its
  own component. It is not blank and not a red error.
- Every AI draft shows its state (`draft`, `approved`, `rejected`) and an approval control.
  Nothing is "sent".
- Show the "Fictional demo data" label on every screen. Show `IllustrativeBadge` on real-institution
  illustrative targets, and `PublicSourceTag` on evidence/signals that carry a stored
  `source_url` (e.g. `PUBLIC_VERIFIED` signals).
- Use one Premium Hybrid theme for F1–F6 (`UI_UX_DESIGN.md` §2). Do not invent per-feature palettes.
- Open an external source link in a new tab with `rel="noopener noreferrer"`, and only from a stored
  `source_url`.
- Evidence is one click away from every claim (evidence drawer).
- Desktop first. Do not hide scores, evidence, or AI labels at narrow widths.
- Meet the accessibility basics in `UI_UX_DESIGN.md`: contrast, visible focus, keyboard, labels,
  meaning not by color alone.

## Auth

Signed-out users go to `/login` (Clerk). A 401 clears the session and returns to login. There is
one role, so there is no no-role page.

## Do not

- Create test files unless explicitly asked.
- Edit `backend/` code.
- Polish a should-have screen while the current phase's manual checks fail.
