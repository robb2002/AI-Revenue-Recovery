# Product PRD — AI Revenue Recovery & Deal Intelligence Agent

**Status:** DRAFT — pending approval (batch 1).
**Source proposal:** `AI_Revenue_Recovery_Deal_Intelligence_Proposal.docx` (hackathon proposal).
**Seller in the demo:** Lumora Learning (fictional). All data is fictional.

## Purpose of this document

This document defines what the product is, who it is for, what each of the six features must do,
what is in and out of the MVP, and how success is judged. It is the first source of truth after
`AGENTS.md`. Technical, data, API, AI, and UI documents must respect it.

---

## 1. Product overview

The AI Revenue Recovery & Deal Intelligence Agent is a single platform that follows one B2B
education deal from a forgotten lead to a post-sale handoff. It reads sales data, finds deals that
may need attention, extracts customer context, retrieves approved answers, drafts the next
message, and prepares the handoff. A human reviews and approves every output.

It is **one connected workflow with six AI capabilities**, not six disconnected tools:

```
Find → Assess → Understand → Resolve → Move forward → Preserve
 F1      F2        F3          F4          F5            F6
```

## 2. Business problem

Sales teams that manage hundreds of leads and active deals lose opportunities not only when a
customer says no, but because leads are forgotten, high-value deals go quiet, meeting details are
not recorded, customer questions stay unanswered, follow-ups take too long, and customer context
disappears after a deal closes.

**Validation note.** These are common B2B sales challenges and a realistic hypothesis. This
product does not claim that any specific company has all these problems or lacks existing tools.
The hackathon demo uses fictional data.

## 3. Pain points and the feature that addresses each

| # | Pain point | Feature |
|---|---|---|
| 1 | Valuable leads are forgotten | F1 Lost Lead Recovery |
| 2 | High-value deals are not prioritized early enough | F2 Revenue Risk Prioritizer |
| 3 | Customer information gets lost after meetings | F3 Meeting Intelligence |
| 4 | Deals stall because questions stay unanswered | F4 Deal Blocker Resolution |
| 5 | Follow-ups and proposals take too much time | F5 Follow-up & Proposal Generator |
| 6 | Customer context disappears after a deal closes | F6 Customer Handoff |

## 4. Target user

**Sales Representative (`SALES_REP`)** — the only role. They:

- review which inactive leads and open deals need attention;
- understand why each was flagged and open the evidence;
- upload meeting notes and review extracted requirements;
- ask a blocker question and read a sourced answer;
- review, edit, approve, or reject drafts;
- mark a deal won and review the handoff.

There is no manager view, no role switch, and no assignment filter. One signed-in user sees all
data.

## 5. Target customers in the demo

The planted core is fictional US education organizations: universities, community colleges, K-12 districts, and a
small number of corporate learning customers. Names, people, emails, and documents are invented
and use clearly fictional patterns. Currency is USD.

Three **real** US public institutions are added as illustrative lead targets (§25a). Their names
are real; their deals, contacts, and activities are fictional and labelled as such.

## 6. Product vision

A sales rep opens the product and sees what needs attention today, why, and what to do next, with
the evidence one click away. The system prepares the work. The rep decides.

## 7. Core workflow

```
Import sample CRM data
 → Detect inactive / lost leads (F1)
 → Score and rank open deals by risk (F2)
 → Extract requirements from a meeting (F3)
 → Retrieve approved answers to blockers (F4)
 → Draft follow-up or proposal (F5)
 → Human approves
 → Mark deal won
 → Generate handoff (F6)
```

A flag is never treated as a certain outcome. Every step shows evidence and waits for a human.

---

## 8. F1 — Lost Lead Recovery

**User story.** As a rep, I want a prioritized list of inactive or lost leads worth reviewing, with
the reason, so I can reconnect with the right customers.

**Behavior**
- Considers deals with status `lost` or `postponed`, and open deals with long inactivity beyond the
  recovery threshold.
- Computes a **recovery priority score (0–100)** and band (`high`, `medium`, `low`) with rules.
- Factors (weights and thresholds are defined in `docs/AI_RAG_DESIGN.md` and approved before
  build): time since last contact, deal value, whether the loss or postpone reason may have
  changed, a fresh company signal, and depth of prior engagement.
- Shows for each lead: last interaction, loss or postpone reason, deal value, requirements known,
  and any company signal, each as a `fact` with evidence.
- The model writes the `interpretation` ("why this lead may be worth reviewing") and the
  `recommended_action`, using only the stored facts.
- Drafts a personalized re-engagement email in state `draft`.

**Acceptance criteria**
1. Lists at least the planted inactive/lost leads, ranked, with a band.
2. Each lead opens an evidence view showing the stored records behind the flag.
3. The previous objection is quoted in the draft only when it is in a stored record.
4. A company signal is cited only if it exists in `company_signals`.
5. The draft cannot be sent, only approved or rejected.
6. A healthy, recently active deal is not listed.

**Measures (pilot, not MVP):** inactive leads reviewed, response rate, meetings booked,
opportunities reopened. A reopened opportunity is not recovered revenue.

## 9. F2 — Revenue Risk & Opportunity Prioritizer

**User story.** As a rep, I want open deals ranked by urgency and impact, with the evidence, so I
know what to act on today.

**Behavior**
- Applies to deals with status `open`.
- Computes a **risk score (0–100)** and band (`high`, `medium`, `low`) with rules.
- Factors: deal value, stage, days since last activity, expected close date proximity, and
  documented risk signals (unanswered blocker, missed meeting, pending security review).
- Shows the five factor contributions with the score, so the number is explainable.
- The model explains the stored score in plain language and recommends an action. It never sets
  the score.
- Shows **at-risk value** as a total of flagged open deals' value. This is labelled "at-risk
  value, not lost revenue".

**Acceptance criteria**
1. A large deal with long inactivity and a near close date ranks above a smaller deal that is
   progressing.
2. Each warning lists the activity or record that triggered it.
3. The ranking is reproducible: the same data and as-of date give the same scores.
4. The score and the explanation are always shown together.
5. A healthy deal is not flagged high.

**Measures (pilot):** high-risk deals reviewed, overdue actions completed, risks resolved,
changes in deal progression.

## 10. F3 — Meeting Intelligence Extractor

**User story.** As a rep, I want to paste or upload meeting notes and get structured customer
context, so nothing is lost.

**Behavior**
- Accepts pasted text or an uploaded `.txt` or `.json` transcript linked to a deal. No PDF.
- **Audio upload (should-have).** The rep uploads a short meeting recording; a free speech-to-text
  service (Groq Whisper) turns it into text. The rep reads and edits that text before saving. The
  audio is not stored. Text from audio is labelled machine-transcribed and may contain errors.
  Extraction then works on the saved text exactly as for pasted text. If speech-to-text is
  unavailable or rate-limited, the rep pastes text instead.
- Extracts: requirements, integration needs, budget and timing, decision-makers, objections and
  blockers, deadlines, and next steps.
- Each extracted field has a status: `confirmed` (stated by the customer), `unconfirmed`
  (mentioned but conditional or vague), or `unknown` (asked but not answered).
- Every extracted item carries a verbatim snippet from the transcript.
- Produces a short summary for the rep to review and save.
- Saving updates the deal's stored context. It does not change the deal stage or status.

**Acceptance criteria**
1. For the demo transcript it identifies the 5,000-student requirement, the integration need,
   the budget approval pending next month, and the IT security questions.
2. Items the customer did not confirm are labelled `unconfirmed` or `unknown`.
3. No extracted item lacks a verbatim snippet. Items without one are dropped.
4. The rep can edit and save the result, or discard it.

**Measures (pilot):** summary preparation time, field completeness, missed next steps identified.

## 11. F4 — Deal Blocker Resolution Agent

**User story.** As a rep, I want a sourced answer to a customer question from approved documents,
so I can respond quickly and accurately.

**Behavior**
- Takes a blocker from an extracted meeting item or a typed question.
- Retrieves passages from the approved knowledge base (fictional Lumora Learning documents) and
  drafts an answer using only those passages.
- Shows each supporting passage with document title, version, and verbatim snippet.
- Returns an **answer status**: `answered`, `partially_answered`, or `insufficient_evidence`.
- When evidence is missing it states what is not confirmed and suggests who to ask (for example the
  security team). It does not guess.
- Does not call the model when retrieval finds nothing above the similarity gate.

**Acceptance criteria**
1. A question about LMS integration with a documented platform returns `answered` with a citation.
2. A question about a platform or capability not in the documents returns
   `insufficient_evidence` with no invented detail.
3. Every claim in the answer maps to a cited passage.
4. The answer is a draft for the rep to review, never sent.

**Measures (pilot):** time to prepare a response, percentage of answers supported by approved
documents, blockers resolved.

## 12. F5 — Follow-up & Proposal Generator

**User story.** As a rep, I want a tailored follow-up or proposal outline drafted from what we know,
so I spend less time writing.

**Behavior**
- Uses confirmed requirements from F3, relevant products from the catalogue, known objections,
  previous interactions, and any F4 answers.
- Generates a `followup_email` or `proposal_outline`.
- Includes only capabilities that exist in the product catalogue and confirmed knowledge-base
  passages. Open items (unconfirmed integration, pending security question) appear in an
  "Open questions" section, not as promises.
- Runs a completeness check and lists missing information.
- Never states a price, discount, term, or commitment that is not in the catalogue or policy
  documents. If a price is needed, it uses "custom quote" or the stored price band.
- State starts as `draft`. The rep edits, approves, or rejects. Nothing is sent.

**Acceptance criteria**
1. The proposal outline for the demo college covers objectives, relevant capabilities, confirmed
   integration details, implementation discussion, open security questions, and next steps.
2. No capability, price, or term appears that is not in stored data.
3. Missing information is listed explicitly.
4. Approving a draft changes only the draft state.

**Measures (pilot):** draft preparation time, drafts accepted with minor edits, follow-ups
completed on time.

## 13. F6 — Customer Handoff Intelligence

**User story.** As a rep, when a deal is won, I want a structured handoff so delivery has the full
context.

**Behavior**
- Triggered by the rep explicitly marking a deal `won`. Nothing marks a deal won automatically.
- Collects stored data: CRM record, saved meeting extractions, approved proposals, activity
  history, customer history, and answered blockers.
- Produces a structured handoff: objective, stakeholders, requirements, integrations, documented
  commitments, dependencies, open questions, risks, and an implementation checklist.
- Each commitment cites its source. Anything not documented is listed under open questions, not
  asserted.
- State starts as `draft`; the rep approves it.

**Acceptance criteria**
1. For the demo deal the handoff lists the 5,000-student objective, integration needs, recorded
   stakeholders, approved commitments, the open security review, and next steps.
2. No commitment appears without a source record.
3. The checklist contains only items derived from stored data.

**Measures (pilot):** handoff completeness, preparation time, missing requirements found before
kickoff, time from closure to kickoff.

---

## 14. Revenue dashboard ("Today's briefing")

The first screen after sign-in.

- **Metrics:** pipeline value, open deals, inactive/lost leads flagged, high-risk deals, at-risk
  value (labelled "not lost revenue"), drafts awaiting approval.
- **Briefing:** the top items needing attention today, each with its score band, one-line reason,
  and a link to its detail. The ranking is rule-based; any sentence is an explanation of a stored
  value.
- **Lists:** recovery leads (F1) and risk deals (F2).
- **Charts (should-have):** pipeline by stage; at-risk value by band.
- **Label:** "Fictional demo data" is visible.

## 15. Deal detail

A single page per deal showing: company, contacts, value, stage, status, last activity, timeline
of activities, signals, flags with evidence, saved meeting extractions, answered blockers, drafts,
and handoff. Actions: reopen a `postponed` or `lost` deal (an explicit rep action that records an
audit entry and does not claim recovery), upload meeting, ask a blocker question, generate a draft,
mark won.

## 16. Evidence requirements

Every important output carries evidence:

| Evidence field | Rule |
|---|---|
| Source type | One of `crm_deal`, `activity`, `company_signal`, `transcript`, `kb_chunk` |
| Source record | Stored record id or document title and version |
| Source URL | Only for a public source the backend fetched and stored, with its fetch date and whether it was fetched live or loaded from a cached snapshot. Otherwise none |
| Date | The record's date, or `unavailable` |
| Snippet | Verbatim substring of the stored source |
| Relationship | How it supports the claim |

An output with no evidence is not stored or shown. The model never creates evidence.

## 17. Human approval

Every draft (`reengagement_email`, `followup_email`, `proposal_outline`, `handoff`) is created in
state `draft`. The rep can edit, approve, or reject. Approval records who and when. There is no
send action. The UI states "Approval does not send anything."

## 18. Truthfulness rules

- Do not invent product features, prices, contractual terms, customer signals, or commitments.
- If evidence is insufficient, say so.
- Flag and score values are calculated by rules from stored data.
- **At-risk value is not lost revenue. Reopened is not recovered.** The product never reports
  recovered revenue in the MVP.
- Do not mark a deal recovered or won because a draft was generated.

## 19. Data strategy

All data is synthetic and fictional, imported from sample files into the application's database.
Datasets: companies, contacts, deals, activities, company signals, customer history, meeting
transcripts, knowledge-base documents, and product catalogue. Details are in
`docs/DATA_SOURCES.md`. Every screen shows "Fictional demo data".

The one exception is the public-source layer (§25a): real institution names and real public signals
fetched from verified official pages, shown with their source URL and always labelled. CRM records
for those institutions stay fictional.

## 20. MVP scope

### Must-have
1. Sample data import and reset.
2. Clerk sign-in with the single role.
3. Dashboard with metrics and briefing.
4. F1 lead list with recovery score, evidence, and re-engagement draft.
5. F2 risk ranking with five factors, explanation, and evidence.
6. F3 transcript upload, extraction with snippets, save.
7. F4 retrieval-backed answers with citations and `insufficient_evidence`.
8. F5 follow-up and proposal drafts with approval states.
9. F6 mark won and handoff draft.
10. Evidence drawer on every claim.

### Should-have
- Public-signal enrichment for three real institutions (§25a), shipped as a cached snapshot with an
  optional live refresh.
- Charts on the dashboard.
- Draft editing history.
- Completeness check display in F5.
- Pilot metrics page with illustrative values.
- Audio upload with speech-to-text for F3 (the pasted-text path stays the must-have).

### Nice-to-have
- Optional read-only HubSpot importer.
- Export of a draft to a text file.

Cut order if time slips: nice-to-have, then should-have, then reduce chart polish. Never cut
evidence, the rules score, human approval, or the insufficient-evidence response.

## 21. Out of scope

Email sending, CRM write-back, live CRM sync (except the optional stretch), calendar integration,
PDF transcripts, live or streaming call transcription, speaker identification, multi-user roles, manager dashboards, notifications, analytics beyond
the dashboard, mobile app, real customer data, and any model-set score.

## 22. Success criteria

The demo succeeds if a judge can:
1. See a prioritized briefing from imported data.
2. Open a flagged deal and see the rule factors and evidence.
3. Upload a transcript live and see structured extraction with snippets.
4. See a blocker answered with a citation, and another refused as `insufficient_evidence`.
5. See an approved-able draft that contains no invented facts.
6. Mark a deal won and see a sourced handoff.
7. See the pilot metrics the team would track, labelled illustrative.

## 23. Hackathon demo workflow

1. Sign in; import sample CRM data.
2. Briefing shows a recoverable lead and a high-value stalled deal.
3. Open the lead: reasons, evidence, re-engagement draft.
4. Upload a held-back transcript; review extraction.
5. Ask three blocker questions that show all three answer statuses: the Canvas LMS integration
   question (`answered`), the non-US data hosting question (`partially_answered`), and the
   Brightspace LMS integration question (`insufficient_evidence`).
6. Generate a proposal outline; approve it.
7. Mark the deal won; review the handoff.
8. Show the pilot metrics slide.

## 24. Planted demo scenarios

| Scenario | Purpose |
|---|---|
| Community college deal postponed for budget, later board-approved signal | F1 hero |
| Large university deal silent 20+ days, close date near, security review pending | F2 hero |
| Smaller deal progressing with meeting confirmed | F2 ranking contrast |
| Healthy recent deal | Negative control (not flagged) |
| Transcript with 5,000-student requirement and security questions | F3 |
| Documented Canvas LMS integration | F4 `answered` |
| Hosting documented for US regions only; non-US hosting not documented | F4 `partially_answered` |
| Brightspace LMS integration not documented anywhere | F4 `insufficient_evidence` |
| Three real institutions with illustrative lost or postponed deals and real public signals | F1 enrichment (should-have). Outcomes are not planted and vary with the real signals |
| Deal with full history | F6 handoff |

The exact data is defined in `docs/DATA_SOURCES.md`.

## 25. Optional stretch: live CRM import

A read-only import from a free CRM account (for example HubSpot) into the same tables, labelled
"live CRM sync". It is nice-to-have, built only after all must-haves pass, and does not change the
data model. `NEEDS VERIFICATION`: free-tier limits and field availability.

## 25a. Public-signal enrichment for real institutions (hybrid, should-have)

**User story.** As a rep, I want to see real, citable public updates from institutions I might
reconnect with, so a recovery lead rests on something that actually happened.

**Behavior**
- Three real US public institutions are tracked. Each has one illustrative lost or postponed deal
  (fictional amount, dates, reason, and contacts), labelled "Illustrative CRM record, not an actual
  relationship with this institution".
- Real signals come from a curated list of verified official pages per institution (newsroom,
  board minutes, announcements). There is no open web search and no crawling.
- A model classifies page text into the five closed signal types and quotes the exact sentence. The
  system stores the real page URL, the fetch time, and the verbatim snippet. The URL is never
  produced by the model.
- A cached snapshot of previously fetched signals ships with the project and loads at import. A
  "Check for new signals" action refreshes one institution live. Pages disallowed by `robots.txt`
  are skipped.
- Real signals feed the same recovery rules. Their scores vary with what the pages contain and are
  **not** part of the planted validation targets.

**Acceptance criteria**
1. Each real signal shows the source URL, fetch date, `live` or `cached snapshot`, and a verbatim
   snippet that appears on the stored page text.
2. No real institution is described as a customer or as having said anything the snippet does not
   say.
3. A fetch failure or a `robots.txt` block records a status and creates no signal.
4. Import and reset make no network calls.
5. The demo works with the snapshot alone.

**Not built:** open web search, a search API, crawling beyond the listed pages, JavaScript-rendered
pages, login-protected pages, personal contact details.

## 26. Pilot measurement (illustrative)

The pilot would measure: inactive leads reviewed, response rate, meetings booked, opportunities
reopened, high-risk deals reviewed, overdue actions completed, summary preparation time,
blocker response time, evidence-backed answer percentage, draft acceptance, and handoff
completeness. The demo shows illustrative placeholder values clearly labelled as such. Financial
impact is estimated only after a pilot with real baselines.

## 27. Risks and assumptions

| Risk | Mitigation |
|---|---|
| LLM latency during live upload | Loading state; pre-tested transcript; stored results for hero deals |
| Model invents a detail | Evidence validation; verbatim snippet check; insufficient-evidence path |
| Weak retrieval on a short knowledge base | Short, specific documents; similarity gate; test the planted questions |
| Judges question realism | Fictional label; validation note; no uniqueness claim |
| Shared Supabase project | Separate schema; no changes outside it |
| Real institution implied to be a customer | Illustrative label on every related record; fictional contacts; wording rules in `AGENTS.md` |
| Live page fetch fails or changes during the demo | Cached snapshot is the default; live refresh is optional |
| A site disallows automated access | Verify `robots.txt` per page before use; skip disallowed pages |
| Real signals change lead scores unpredictably | Planted core remains deterministic; real leads are excluded from validation targets |

## Open questions

0. **Decided: hybrid.** Fictional planted core plus three real institutions with real public
   signals from curated official pages (§25a). Which three institutions is decided in Phase 0.
1. ~~Should the Clerk application be the same as the parent project or a new one?~~ **Decided:
   reuse the same Clerk application.**
2. ~~Pre-generate explanations at import or on first open?~~ **Decided: pre-generate for the
   hero deals at import; all other deals generate on first open and are stored.** An LLM failure
   during import does not fail the import (see `docs/AI_RAG_DESIGN.md`).
3. ~~Should the demo's fixed "today" date be set now?~~ **Decided: set in `docs/DATA_SOURCES.md`
   (`DEMO_AS_OF_DATE`).**
4. ~~Is the optional HubSpot import wanted at all?~~ **Decided: yes, as a read-only
   nice-to-have stretch (§25), built only after every must-have passes.**
