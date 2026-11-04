# Authentication and Authorization — AI Revenue Recovery & Deal Intelligence Agent

**Status:** DRAFT — pending approval (batch 2).

## Purpose of this document

This document defines sign-in, token verification, the single role, route protection, and error
behavior. It uses the same pattern as the Excelsoft AI Sales Intelligence System: **Clerk answers
who the user is; FastAPI verifies and answers what they may do.** The only simplification is that
there is **one role**, `SALES_REP`, so there is no role metadata, no role-based 403, and no
permission matrix.

---

## 1. Architecture

```
User → React → Clerk sign-in → Clerk session token
     → FastAPI (Authorization: Bearer <token>) → verify token → identify Clerk user
     → upsert app_users row → handler runs
```

One check runs on every protected request:

1. **Authentication.** The token is present, well-formed, signed by this Clerk instance, and
   unexpired. Failure is `401` and the request never reaches business logic.

There is no second check. Every authenticated user is a `SALES_REP`.

The frontend repeats a weaker check to keep anonymous visitors off the screens. The backend check
is the real one: a client that skips the redirect and calls the API directly is still rejected.

## 2. Decision: same Clerk application

This project **reuses the Clerk application of the parent project**. The same Clerk secret key,
publishable key, and development instance are used. Consequences:

- A user who can sign in to the parent app can sign in to this app. The parent app's role metadata
  (`publicMetadata.role`) is ignored here. This app does not read it.
- Clerk user ids are the same in both apps; each app keeps its own `app_users` row in its own
  schema.
- The Clerk Dashboard must allow this app's origin (local `http://localhost:5173` and the hosted
  origin). That setting lives in Clerk, not in this repository.

Known limitation, recorded for the demo: there is no isolation between the two products' user
pools. Acceptable for a hackathon. A separate Clerk application is the fix and needs only new keys.

## 3. Clerk responsibilities

| Responsibility | Clerk | This application |
|---|---|---|
| Sign up, sign in, sign out | Yes | No custom forms |
| Passwords, reset, hashing | Yes | Never stored or handled |
| Session creation, refresh, expiry | Yes | Never |
| Token issuance | Yes | The backend only verifies |
| Identity (user id, email) | Source of truth | Email is copied into `app_users` |

Login method: email and password through Clerk. Social login and enterprise SSO are out of scope.
The React app uses Clerk's sign-in component on `/login`, themed toward the project tokens as far
as Clerk's appearance options allow.

## 4. FastAPI responsibilities

| Responsibility | Rule |
|---|---|
| Verify the bearer token on every protected route | One shared dependency, not per-route code |
| Read the Clerk user id from the verified token | The only identity the backend trusts |
| Reject missing, invalid, and expired tokens | `401` before any database write |
| Upsert the application user | `app_users` keyed by Clerk user id |
| Never trust client-sent identity | A user id or role sent in a body or header is ignored |

Verification uses PyJWT with the signing keys Clerk publishes for this instance, obtained with the
Clerk backend secret. Signature, expiry, and issuer are checked every time.
`NEEDS VERIFICATION` at implementation: the exact key-retrieval call, matching what the parent
project uses.

## 5. Flow

**Sign in**
1. A visitor opens any route and is redirected to `/login`.
2. Clerk signs the user in. Clerk's SDK holds the session. The app stores no token itself.
3. The API client asks Clerk for a session token and sends `Authorization: Bearer <token>`.
4. FastAPI verifies the token. On success it loads the Clerk user's email from Clerk using the
   backend secret (cached briefly), and upserts `revenue_recovery.app_users`.

**While signed in.** Clerk refreshes the session. The backend is stateless.

**Sign out.** The UI calls Clerk sign-out, clears the TanStack Query cache, and navigates to
`/login`. There is no backend logout endpoint. Old tokens fail verification and return `401`.

## 6. Role model

| Role | Code | Capabilities |
|---|---|---|
| Sales Representative | `SALES_REP` | Every protected endpoint: view, import, reset, extract, answer, draft, approve, reject, reopen, mark won |

Rules:
- The role is constant. `app_users.role` is always `SALES_REP`.
- There is no assignment filter. Every rep sees every company and deal.
- Approval records which user approved. It does not require a second person.
- Sign-up does not need role metadata in Clerk.

A future second role is a schema, API, and middleware change recorded through the documents first.

## 7. Frontend route protection

| Route | Access |
|---|---|
| `/login` | Public |
| Every other route | Requires a Clerk session. Otherwise redirect to `/login` |

- Signed-out users never see application chrome.
- A `401` from any API call clears the session cache and navigates to `/login`.
- The sidebar footer shows the user's name or email and a sign-out action.
- There is no "no role" page.

## 8. Backend route protection

- Every router under `/api/v1` is protected by default through one dependency.
- `GET /api/v1/health` is the only public route. It returns no application data.
- `GET /api/v1/me` returns the verified user.
- Import and reset are protected like any other route. They are rep actions in the demo.
- Authorization needs no per-route annotation. A new route is protected unless it is explicitly
  listed as public in a single allowlist.

## 9. User data

`revenue_recovery.app_users` stores `id`, `clerk_user_id` (unique), `email`, `role`
(`SALES_REP`), `created_at`, `updated_at`, `last_seen_at`.

Not stored: password, password hash, session token, refresh token, Clerk secret. The display name
stays in Clerk and is read client-side.

A row is created or updated on every successful verification. `last_seen_at` is updated at most
once per minute to avoid a write on every request.

## 10. Errors

Auth failures use the shared error envelope in `docs/API_CONTRACT.md`.

| Situation | HTTP | Code |
|---|---|---|
| No `Authorization` header or empty bearer token | 401 | `AUTH_MISSING` |
| Malformed, unsigned, or foreign-instance token | 401 | `AUTH_INVALID` |
| Expired token | 401 | `AUTH_EXPIRED` |
| Clerk unreachable while verifying or loading the user | 401 | `AUTH_INVALID` (fail closed) |

There is no 403 for roles. `401` messages stay generic and never include the token, the secret, a
stack trace, or whether another user exists.

## 11. Security rules

| Rule | Requirement |
|---|---|
| Verification | Every protected request. A decoded but unverified token is never trusted |
| Clerk secret | `CLERK_SECRET_KEY` on the backend only. Never in frontend code, env, logs, or git |
| Publishable key | `VITE_CLERK_PUBLISHABLE_KEY` is the only Clerk value in the frontend. Placeholders in `.env.example` |
| Passwords | Never received or stored by FastAPI |
| Tokens in logs | Never logged |
| Transport | Plain HTTP on localhost for the demo. HTTPS if ever hosted |
| CORS | Allowlist is the frontend origin only. It is not an auth mechanism |
| Fail closed | If Clerk is down, the API returns `401`. No local password fallback |
| Data isolation | Auth never grants access outside the `revenue_recovery` schema |

## 12. Environment variables

| Variable | Process | Purpose |
|---|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | Frontend, build time | Clerk browser SDK |
| `CLERK_SECRET_KEY` | Backend | Verify tokens and load the user |
| `CORS_ALLOWED_ORIGINS` | Backend | Allowed frontend origin |

No `JWT_SECRET`. The backend never signs tokens.

## 13. Local development

1. Use the parent project's Clerk development instance (same keys, copied into this project's
   untracked `.env` files).
2. Add `http://localhost:5173` to the allowed origins in the Clerk Dashboard.
3. One demo user in Clerk is enough. It needs no role metadata.
4. The first successful `GET /api/v1/me` creates the `app_users` row.

## 14. Demo environment (localhost)

- **Decided:** the demo runs on localhost with the same Clerk application as the parent project, used
  for sign-in only. There is no hosted deployment and no separate Clerk instance.
- Keys live in local `.env` files, never in code or git.
- A Clerk or network outage blocks sign-in; the API returns `401`. Keep a signed-in browser session
  open before the demo.

## 15. MVP scope and out of scope

In scope: Clerk email/password sign-in, token verification, `app_users` upsert, `GET /me`, default-on
protection, route guard, sign-out with cache clear.

Out of scope: multiple roles, role metadata, social login, enterprise SSO, MFA customization, custom
password rules, API keys, per-user data isolation, organization or team management, admin screens.

## Open questions

1. Same Clerk application is decided (§2). Confirm the origin list in Clerk includes
   `http://localhost:5173`.
2. Confirm how the parent project retrieves Clerk signing keys, and reuse that call.
3. ~~Hosted demo: same or separate Clerk instance?~~ **Decided: localhost, same Clerk application.**
