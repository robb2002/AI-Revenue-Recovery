# Feature 1 PRD — Lost Lead Recovery Engine

**Status:** READY FOR EVENT IMPLEMENTATION  
**Feature key:** `lead_recovery`  
**Owner folders:** FE `frontend/src/pages/f1_recovery/` (+ optional `features/f1_recovery/`);  
BE `backend/app/api/routes/f1_recovery.py`, `backend/app/services/f1_recovery.py`,
`backend/app/services/f1_gmail.py`  
**Branch:** `feat/f1-recovery`

---

## 0. How to use this PRD

1. Read `docs/features/README.md` (parallel module rules — **mandatory**).  
2. Implement UI only with tokens/components from `docs/UI_UX_DESIGN.md`.  
3. Call only F1 (+ shared account) endpoints in `docs/API_CONTRACT.md` §5–§6.  
4. Read/write only columns listed here from `revenue_recovery.crm_master`
   (`docs/DATABASE_DESIGN.md`).  
5. Ground AI with `docs/AI_RAG_DESIGN.md`. Demo data anchors: `docs/DATA_SOURCES.md`.  
6. Use **§14 sample drafts + §15 sample Gmail threads** in development instead of inventing copy.  
7. Do **not** generate automated test files unless explicitly asked.

This PRD is the full build brief for F1: recovery list/detail, re-engagement draft (human
approve), **real Gmail API thread sync**, CRM log-after-approve, reopen, and judge demo.

---

## 1. Goal (judge-facing)

Help a salesperson **find inactive or lost opportunities worth revisiting**, see **why** (with
evidence), get a **draft re-engagement email** to approve, and **sync real Gmail** for that lead’s
contact address so **previous vs new messages** appear with valid Gmail sources. Logging outreach
into CRM still requires **human confirmation**. The system never marks a deal “recovered” and
**never sends** email by itself (Gmail is **read** for history; send remains outside the app or a
future explicit Send — out of MVP).

**One-line pitch:** “Draft you control, real inbox thread for the lead, CRM update only when you
approve — we don’t invent recovered revenue.”

---

## 2. Parallel development contract (F1-specific)

| Area | F1 owns | Must not modify |
|---|---|---|
| Routes UI | `/recovery`, `/recovery/:accountId` | Other feature routes; global shell except nav registration |
| API | `/recovery`, `/accounts/{id}/recovery`, reengagement draft, **Gmail connect/sync/thread**, CRM email-log preview/confirm, reopen | F2–F6 route modules |
| Services | Candidate filter, explanation, draft orchestration, **Gmail OAuth + fetch**, CRM log apply | Open-deal **risk** (F2); meetings (F3); KB (F4) |
| Shared | `crm_master` repository + auth | No new CRM lead tables (Gmail tokens may use a small non-CRM store — see §6.7) |

---

## 3. User stories

1. As a sales rep, I see a **ranked list** of lost/inactive accounts that may be worth reviewing.  
2. As a sales rep, I open one account and see **facts / interpretation / recommended action** with evidence.  
3. As a sales rep, I generate or use a **sample re-engagement draft**, edit it, and **approve/reject**.  
4. As a sales rep, I **connect Gmail** (once) and click **Sync Gmail** on a lead to load messages
   matched to that lead’s `contact_email`.  
5. As a sales rep, I see **Previous** and **New** messages for the same address, each with a valid
   Gmail source (message id, date, from/to).  
6. As a sales rep, I **log** either the approved draft summary or a selected Gmail message into CRM
   only after preview + confirm.  
7. As a sales rep, I may **explicitly reopen** an opportunity — never automatic.  

---

## 4. Scope

### 4.1 In scope (MVP must)

- Recovery list: `lost` / `inactive` + `recovery_eligibility` in `eligible` | `review`.  
- Detail: layered explanation + PUBLIC_VERIFIED signal.  
- **Re-engagement draft:** generate/refresh **or** load §14 sample; edit while `draft`;
  approve/reject content. Approval ≠ send.  
- **Real Gmail API (read):**
  - OAuth connect for the salesperson’s mailbox.  
  - **Sync Gmail** on an account: query messages involving `contact_email` (To/From/Cc).  
  - UI thread: **New** (since last sync / unread / after last CRM activity date) vs **Previous**.  
  - Each row cites `gmail_message_id`, date, from, to, snippet (verbatim).  
- **CRM log sync** (rename of prior “email sync”): preview → confirm → write activity on
  `crm_master` (from approved draft **or** selected Gmail message). Does not reopen.  
- Explicit **Reopen** with confirm.  
- **Offline / no-Gmail demo path:** use §15 fixture threads so UI still demos Previous/New.  
- Fictional demo badge; empty/loading/error/AI-unavailable/Gmail-disconnected states.

### 4.2 Out of scope (F1)

- Auto-**send** via Gmail API (no Send button in MVP).  
- Full mailbox crawl unrelated to the lead’s `contact_email`.  
- Marking won / handoff (F6), risk (F2), meetings (F3), KB (F4), proposals (F5).  
- New CRM business tables for deals.  
- Automated test suites.

### 4.3 Should-have

- Sort by value / inactivity / eligibility.  
- Diff UI for CRM log preview.  
- Store `last_gmail_sync_at` on row or in sync metadata.  
- Deep link from dashboard into `/recovery/:accountId`.

---

## 5. Data (`crm_master`)

### 5.1 List / filter / detail reads

Same as before: identity, `deal_status`, `recovery_eligibility`, value, lost reason, inactivity,
signal fields (`PUBLIC_VERIFIED` URL only from DB), draft columns, contact fields including
**`contact_email` (Gmail match key)**, requirements/objections, `activity_history`,
`as_of_date` (`2026-11-04`), fictional label.

### 5.2 Writes (human confirm only)

| Action | Columns |
|---|---|
| Draft edit / generate | `followup_email_subject`, `followup_email_body`, `followup_message_status=draft` |
| Approve draft content | `followup_message_status` → `approved` (or keep draft until CRM log — **recommend:** Sync Gmail does not change draft state; **CRM log confirm** or content Approve sets `approved`) |
| Reject draft | `followup_message_status` → `rejected` |
| **CRM log confirm** | Append `activity_history`; refresh `last_contacted_date`, `last_activity_date`, activity fields; recompute `inactivity_days` from `as_of_date`; set draft `approved` if logging the draft |
| Reopen | `deal_status` → `open`; eligibility cleared; activity note; **never** won |

**Never:** invent Gmail messages; invent `signal_source_url`; set won inside F1.

### 5.3 Demo heroes

| `account_id` | Why |
|---|---|
| `ACC-0178` Arizona State University | lost + PUBLIC_VERIFIED + eligible |
| `ACC-0180` California State University | lost + PUBLIC_VERIFIED + eligible |
| `ACC-0189` The Ohio State University | inactive + PUBLIC_VERIFIED + eligible |

**Gmail demo note:** Plant threads in the demo Gmail account using the **same** `contact_email`
values as on these rows (or override match emails in env for local demo). If live Gmail is not
connected, load §15 fixtures.

---

## 6. Backend design

### 6.1 Modules

```
api/routes/f1_recovery.py
services/f1_recovery.py
services/f1_gmail.py          # OAuth + Gmail API fetch/parse
services/f1_email_crm_log.py  # preview + apply CRM log (former email-sync)
```

### 6.2 Responsibilities

| Method | Behavior |
|---|---|
| `list_recovery_candidates` | Filter + sort; no model |
| `get_recovery_detail` | Facts, evidence, draft, last sync meta |
| `explain_recovery` | Optional AI layers |
| `generate_reengagement_draft` | AI **or** return §14 sample for heroes; state `draft` |
| `gmail_oauth_start` / `callback` | Clerk-user scoped token storage |
| `sync_gmail_for_account` | Fetch by `contact_email`; classify new vs previous; return thread DTO |
| `get_thread` | Cached/last sync result for UI |
| `preview_crm_log` | No write; from draft or `gmail_message_id` |
| `confirm_crm_log` | Transactional CRM update |
| `reopen_opportunity` | Confirm required |

### 6.3 API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/recovery` | List |
| GET | `/api/v1/accounts/{id}/recovery` | Detail |
| POST | `/api/v1/accounts/{id}/drafts/reengagement` | Generate / load sample |
| PATCH | `/api/v1/accounts/{id}/drafts/reengagement` | Edit while draft |
| POST | `.../drafts/reengagement/approve` \| `/reject` | Content state |
| GET | `/api/v1/gmail/connect` | Start OAuth |
| GET | `/api/v1/gmail/callback` | OAuth callback |
| GET | `/api/v1/gmail/status` | Connected? email? |
| POST | `/api/v1/accounts/{id}/gmail/sync` | **Sync Gmail** — fetch thread |
| GET | `/api/v1/accounts/{id}/gmail/thread` | Last synced Previous/New |
| GET | `/api/v1/accounts/{id}/crm-log/preview` | Preview CRM patch |
| POST | `/api/v1/accounts/{id}/crm-log/confirm` | `{ confirm: true, source: draft\|gmail, gmail_message_id? }` |
| POST | `/api/v1/accounts/{id}/reopen` | `{ confirm: true }` |

Legacy alias: `email-sync/preview|confirm` may map to `crm-log/*` for compatibility.

### 6.4 Gmail sync — detailed flow

```
User connects Gmail once (OAuth) → tokens stored for Clerk user
Open recovery detail (has contact_email)
  → Click "Sync Gmail"
  → POST .../gmail/sync
       Query Gmail API: messages where To/From/Cc includes contact_email
       Parse: id, threadId, date, from, to, subject, snippet, labelIds
       Classify:
         NEW = after max(last_activity_date, last_gmail_sync_at) OR UNREAD
         PREVIOUS = older in same match set (cap e.g. 20)
       If Gmail disconnected or DEMO_GMAIL_FIXTURES=1 → return §15 fixtures
  → UI shows two sections: New emails | Previous emails
       Each row: subject, date, from→to, snippet, source chip (gmail_message_id)
  → Optional: select one message → "Log to CRM" → crm-log preview/confirm
```

**Match rules**

- Primary key: exact `contact_email` (case-insensitive).  
- If `contact_email` null/empty → `422 NO_CONTACT_EMAIL`; do not search whole mailbox.  
- Do not invent messages when API returns empty — show honest empty + keep draft path.  
- Multiple messages: **all** matching messages in the window are returned as **separate** rows
  (not merged into one). New vs Previous is classification only.

**What Sync Gmail does *not* do**

- Does not send mail.  
- Does not change `deal_status`.  
- Does not auto-write CRM (that is crm-log confirm).

### 6.5 CRM log (after draft or Gmail message)

Same preview/confirm pattern as before:

- From **draft**: activity description from subject/body summary.  
- From **Gmail**: activity description from selected message subject/snippet; store
  `gmail_message_id` in activity metadata if schema allows (else put id in description).  
- `will_not_change`: deal_status, deal_value, signal URL, “not recovered revenue”.  
- Without `confirm: true` → `422 CONFIRMATION_REQUIRED`.

### 6.6 AI rules

- Draft may use lost reason, contact name, signal title/URL if PUBLIC_VERIFIED, product_reference.  
- Forbidden: will close, guaranteed, is recovered, recovered revenue.  
- AI down: use §14 sample drafts for heroes; list/facts still work.

### 6.7 Gmail token storage

Prefer a **non-CRM** table or encrypted server store scoped by `clerk_user_id` (e.g.
`revenue_recovery.gmail_connections`). Not a second CRM deals table. Document migration in
Platform/F1 PR if created. Tokens never committed to git.

### 6.8 Recovery ranking

Eligible + PUBLIC_VERIFIED first (heroes); else eligibility / inactivity / value. Optional
ephemeral 0–100 per `AI_RAG_DESIGN.md`.

---

## 7. Frontend design

### 7.1 Routes

- `/recovery` list  
- `/recovery/:accountId` detail  

Nav: **Lead Recovery** · `RotateCcw`.

### 7.2 Visual system

Premium Hybrid only (`UI_UX_DESIGN.md` §2): navy primary, indigo AI generate, amber recovery
emphasis, green after successful CRM log / Gmail connected, red only hard errors.

### 7.3 List page

Unchanged intent: filters, heroes near top, PublicSourceTag, draft state column.

### 7.4 Detail page layout

1. **Summary** — account, status, value, inactivity, contact (+ email).  
2. **Why this account** — FACT / INTERPRETATION / RECOMMENDED ACTION + evidence.  
3. **Signal card** — verified URL if stored.  
4. **Gmail thread panel**
   - Connect Gmail / Connected as `…` / Sync Gmail (navy).  
   - Tabs or sections: **New** | **Previous**.  
   - Row: subject, relative date, from, snippet, source `Gmail · {message_id short}`.  
   - Empty: “No messages for this contact email” / “Connect Gmail to sync”.  
   - Fixture badge when using §15: `Demo thread (fixture)`.  
5. **Re-engagement draft** — subject/body, DraftNotice, Generate (indigo) / Load sample,
   Save, Approve/Reject. “Approval does not send email.”  
6. **CTAs**
   - **Log to CRM** (navy) — preview modal (draft or selected Gmail msg).  
   - **Reopen** (secondary).

### 7.5 CRM log approval modal

Title: **Review CRM updates before logging**  
Email/source preview · fields that will update · will not change · Cancel | Confirm.

### 7.6 Reopen modal

Status → open; does not claim recovered revenue.

### 7.7 States

Loading, empty filter, AI unavailable (+ sample draft), Gmail not connected, Gmail API error,
empty thread, preview loading, CRM log success toast, no confetti / no “recovered $”.

---

## 8. End-to-end scenarios

1. **Draft + CRM log (no Gmail):** ACC-0178 → load §14 draft → edit → Log to CRM → confirm →
   activity updates; status still lost → Reopen.  
2. **Real Gmail sync:** Connect → Sync on ACC-0178 → New + Previous rows with real message ids.  
3. **Multi-mail:** Two inbound mails from same contact → **two** Previous/New rows (not one blob).  
4. **Log selected Gmail message** → preview cites that message id → confirm.  
5. **Gmail disconnected:** §15 fixtures still show New/Previous for demo.  
6. **No contact_email:** Sync disabled with clear error.  
7. **AI down:** §14 samples still load.  
8. **Honesty:** never “recovered $X”.

---

## 9. Guardrails

- Human approve before CRM write.  
- No Send button (MVP).  
- No auto-reopen.  
- Gmail read only for matched `contact_email`.  
- No invented messages or signals.  
- Fictional demo label on CRM UI.  
- Single `crm_master` for deal data.

---

## 10. Acceptance criteria (manual)

1. Recovery list includes three PUBLIC_VERIFIED heroes.  
2. Layered claims + evidence; verified URL works.  
3. Draft from generate or §14; approve ≠ send.  
4. Gmail connect + Sync returns thread classified New/Previous with message ids **or** fixtures.  
5. Multiple mails = multiple rows.  
6. CRM log preview accurate; cancel writes nothing; confirm updates activity/dates.  
7. Reopen separate from sync/log.  
8. Premium Hybrid tokens; F1 modules isolated.  
9. Wording compliant.

---

## 11. Demo script (~2–2.5 min)

1. Lead Recovery → **Arizona State** — lost reason + public source.  
2. Show **sample/AI draft** — “salesperson still approves; we don’t send.”  
3. **Sync Gmail** (or fixture) — point at **New** vs **Previous** + source ids.  
4. **Log to CRM** → preview will/won’t change → Confirm → timeline updates.  
5. Optional Reopen — “still not calling it recovered.”

---

## 12. Dependencies

| Need | From |
|---|---|
| Auth, shell, API client | Platform |
| Google Cloud OAuth client (Gmail readonly scope) | Phase 0 env |
| Demo mailbox with planted threads (optional live) | Ops |
| Risk / meetings / KB | Not required |

---

## 13. Open questions

1. Reopen target stage — recommend `open` + Discovery.  
2. Gmail scopes — recommend `gmail.readonly` only for MVP.  
3. Whether “Approve draft” is required before CRM log — recommend CRM log confirm implies
   draft approval when source=draft.  
4. Token table name — finalize with Platform in Phase 0.

---

## 14. Sample re-engagement drafts (use in development)

Use these verbatim for heroes when AI is off or for UI wiring. `status`: start as `draft`.

### ACC-0178 — Arizona State University

```json
{
  "account_id": "ACC-0178",
  "draft_type": "reengagement_email",
  "followup_email_subject": "Reconnecting on MyLab / learning platform timing at ASU",
  "followup_email_body": "Hi {{contact_name}},\n\nI hope you are well. When we last spoke, the timing for moving forward on the learning platform evaluation was difficult ({{lost_reason}}).\n\nI noticed a recent public update related to AI and learning platforms at ASU and wanted to check whether it is a good moment to reconnect for a short working session—no proposal pressure.\n\nWould any time next week work for a 20-minute check-in?\n\nBest regards,\n{{account_owner}}\nLumora Learning",
  "followup_message_status": "draft",
  "notes": "Replace {{ }} from crm_master at render time. Do not invent prices."
}
```

### ACC-0180 — California State University

```json
{
  "account_id": "ACC-0180",
  "draft_type": "reengagement_email",
  "followup_email_subject": "Checking in — assessment / AI initiative timing",
  "followup_email_body": "Hi {{contact_name}},\n\nI am reaching out because our last conversation paused on timing and priorities ({{lost_reason}}).\n\nGiven recent public CSU/SDSU AI initiative updates on file, I wanted to see if a brief reconnect would help clarify whether Lumora’s assessment tools are still relevant for your team this term.\n\nHappy to work around your calendar.\n\nRegards,\n{{account_owner}}\nLumora Learning",
  "followup_message_status": "draft"
}
```

### ACC-0189 — The Ohio State University

```json
{
  "account_id": "ACC-0189",
  "draft_type": "reengagement_email",
  "followup_email_subject": "AI Fluency follow-up — worth a short reconnect?",
  "followup_email_body": "Hi {{contact_name}},\n\nYou asked us to hold while internal priorities settled (inactivity on file). I saw the AI Fluency–related public update we have on record and thought a light-touch check-in might be useful.\n\nIf helpful, I can send a one-page outline aligned to your last stated needs—still a draft for your review only.\n\nThanks,\n{{account_owner}}\nLumora Learning",
  "followup_message_status": "draft"
}
```

---

## 15. Sample Gmail thread fixtures (use when API off)

Classify against `as_of_date = 2026-11-04`. Treat messages dated **after** `last_activity_date` on
the row as **New**; older as **Previous**. Message ids are **fixture ids** (prefix `fixture_`);
live sync must replace with real Gmail ids.

### ACC-0178 fixture thread

```json
{
  "account_id": "ACC-0178",
  "match_email": "{{contact_email}}",
  "source": "fixture",
  "new_messages": [
    {
      "gmail_message_id": "fixture_asu_new_001",
      "thread_id": "fixture_asu_thread_1",
      "date": "2026-10-28T15:12:00Z",
      "from": "{{contact_email}}",
      "to": "rep@lumora-demo.example",
      "subject": "Re: Timing for MyLab evaluation",
      "snippet": "Thanks for holding — can we revisit after our November planning meeting?",
      "classification": "new"
    }
  ],
  "previous_messages": [
    {
      "gmail_message_id": "fixture_asu_prev_001",
      "thread_id": "fixture_asu_thread_1",
      "date": "2026-03-04T18:00:00Z",
      "from": "rep@lumora-demo.example",
      "to": "{{contact_email}}",
      "subject": "MyLab evaluation next steps",
      "snippet": "Sharing the outline we discussed and proposed pilot scope.",
      "classification": "previous"
    },
    {
      "gmail_message_id": "fixture_asu_prev_002",
      "thread_id": "fixture_asu_thread_1",
      "date": "2026-03-10T14:22:00Z",
      "from": "{{contact_email}}",
      "to": "rep@lumora-demo.example",
      "subject": "Re: MyLab evaluation next steps",
      "snippet": "We need to pause — budget timing is the blocker for this quarter.",
      "classification": "previous"
    }
  ]
}
```

### ACC-0180 / ACC-0189

Mirror the same shape with ids `fixture_csu_*` and `fixture_osu_*`, subjects tied to assessment /
AI Fluency, and one **new** + two **previous** messages each so the UI always has both sections
populated in fixture mode.

**Rule:** live Gmail responses must use the **same DTO shape** so the UI does not branch.

---

## Document history

| Date | Change |
|---|---|
| 2026-11-04 | Initial F1 feature PRD: modules, UI, CRM email-sync approval, demo heroes |
| 2026-11-04 | Added real Gmail API sync (read), New vs Previous thread UI, sample drafts §14, fixtures §15; CRM log remains human-approved; no auto-send |
