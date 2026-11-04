# Backend — Agent Guide

Read the root `AGENTS.md` first. This file does not override it.

**Implement only the backend or AI task in the requested phase of `docs/IMPLEMENTATION_PLAN.md`.**
Finish that phase's manual checks before the next phase.

## Documents you implement

| Document | What you take from it |
|---|---|
| `docs/API_CONTRACT.md` | Paths, bodies, enums, errors, pagination |
| `docs/DATABASE_DESIGN.md` | Tables and columns. Do not rename them |
| `docs/AUTHENTICATION.md` | Clerk token verification, single role |
| `docs/AI_RAG_DESIGN.md` | Extraction, scoring rules, retrieval, grounding, drafting |
| `docs/DATA_SOURCES.md` | Sample files, fields, import rules |
| `docs/TECHNICAL_PRD.md` | Process shape, layering, configuration |
| `docs/IMPLEMENTATION_PLAN.md` | Must / should / nice, and the phase checks |

## Stack

Python, FastAPI, SQLAlchemy async, asyncpg, Alembic, Supabase PostgreSQL with pgvector,
Azure OpenAI through a provider adapter, `text-embedding-ada-002`, PyJWT for Clerk token
verification only, httpx (also used for the Groq speech-to-text call). No APScheduler in the MVP. No Redis, Celery, Kafka, or second service.
One process.

## Layering

```
Routes → services → repositories → PostgreSQL (schema revenue_recovery)
Services → AIService → provider adapter
Import service → repositories
```

Routes validate and authorize. They hold no business rules and no SQL. Services hold no SQL.
Only repositories touch the database. Scoring functions are pure code and never call a model.

## Database isolation

The Supabase project is shared with another application. Every table lives in the
`revenue_recovery` schema. Alembic uses its own version table in that schema. Never create,
alter, drop, or read objects in any other schema. Never run a migration against `public`.

## Auth

Verify the Clerk bearer token, then upsert the user in `revenue_recovery.app_users`. Do not issue
JWTs. Do not store passwords. Do not use Supabase Auth. Missing or invalid token is 401.
`GET /api/v1/health` is the only public route. There is one role, so no role check and no row
filter.

## AI rules

- The scoring function does not call a model. The model explains the stored number.
- The model receives candidate evidence with ids and returns ids and quotes. The backend rejects
  any id it did not supply and any snippet that is not a verbatim substring of the source.
- If retrieval returns nothing above the similarity gate, return `insufficient_evidence` and do
  not call the model.
- Never fabricate a feature, price, date, term, commitment, contact, or source.
- Every draft starts in state `draft`. Nothing is sent.

## Public signal collector (should-have, built in the phase that names it)

- Fetch only URLs from the `institution_sources` table (loaded from the reviewed
  `institution_sources.json`). Never fetch a URL from a request body or a model.
- Check `robots.txt` for each host with our user agent. If disallowed, record `skipped_robots` and
  do not fetch the page.
- httpx with `HTTP_TIMEOUT_SECONDS`, a delay between requests to one host, and the page and signal
  caps from configuration. BeautifulSoup parsing only. No JavaScript rendering, no login, no CAPTCHA
  handling.
- The model classifies and quotes. The stored URL and fetch time come from the collector, never from
  the model. The snippet must be a verbatim substring of the fetched text.
- A failed or empty fetch records its status. It never produces a signal.
- Import and reset never call the network. They load the committed snapshot.

## Speech to text (should-have)

- `TranscriptionService` and one STT adapter send one uploaded audio file to the configured
  provider and return text. They never extract, score, or cite.
- The endpoint returns text only. Do not store the audio, and do not create a meeting from it. The
  rep reviews the text and saves it through the normal meeting endpoint with `source = audio`.
- Enforce the size limit and accepted formats before calling the provider. Never log the audio or
  the STT key. A failure maps to the documented `STT_*` codes and never blocks the text path.

## Do not

- Create test files unless explicitly asked.
- Edit `frontend/` pages.
- Add a dependency to get around a missing contract field.
