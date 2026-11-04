# UI/UX Design — AI Revenue Recovery & Deal Intelligence Agent

**Status:** APPROVED FOR MVP BUILD — Premium Hybrid palette + `crm_master` screens (2026-11-04).  
**Supersedes:** import-centric Data page as a must-have; Cedar Valley / multi-table copy.  
**Contracts:** `API_CONTRACT.md`, `DATABASE_DESIGN.md`, `DATA_SOURCES.md`.

## Purpose of this document

Defines the design system, shared colors, components, and screens for **all six features**. Every
feature uses the same tokens. Implementers copy hex values into Tailwind / CSS variables once;
components use **semantic tokens only** (no raw hex in JSX).

Visual language: **Premium Hybrid** (Excelsoft AI Sales Intelligence family) — navy structure,
indigo for AI only, amber for attention/recovery, green for approved/healthy, red for risk.

---

## 1. Design principles

1. **One product, six features.** Shared shell, typography, and colors. Feature pages differ by
   content, not by theme.
2. **Clean enterprise for work; indigo for AI.** White cards and navy structure for CRM records.
   AI drafts, answers, and extractions sit on AI surfaces.
3. **Evidence is one click away.** No claim without an evidence chip.
4. **Layers are visible.** `fact` / `interpretation` / `recommended_action` never share one
   unlabelled paragraph.
5. **Scores travel with explanation.** Number, band, factors, written explanation together.
6. **Drafts are drafts.** State pill + approval. No "Send".
7. **Honesty is a feature.** `insufficient_evidence` and AI-unavailable are designed states.
8. **Fictional data is always labelled.**
9. **Density for scanning, space for reading.**

### 1.1 Forbidden

Pure black (`#000`), pure grey stacks, decorative gradients, glow/neon, gaming UI, emoji as icons,
unlabelled colored scores, green-to-red heatmaps, a "Send" button, "guaranteed" / "will close" /
"recovered revenue", confetti on mark-won. Do not invent a second purple theme or cream/terracotta
look for individual features.

---

## 2. Color system (mandatory for every feature)

### 2.1 Foundation scales — implement exactly

| Token | Hex | Use |
|---|---|---|
| `navy-50` | `#EEF2F8` | Tinted background, selected row |
| `navy-100` | `#D8E1EF` | Subtle fills |
| `navy-200` | `#B3C3DD` | Borders on navy |
| `navy-300` | `#7F97BE` | Muted text on dark navy |
| `navy-400` | `#4E6B9B` | Focus ring, chart series |
| `navy-500` | `#2F4E7E` | Secondary structure, medium recovery band |
| `navy-600` | `#1E3A66` | **Primary** buttons, links, active nav text |
| `navy-700` | `#172E52` | Primary hover |
| `navy-800` | `#11223D` | Sidebar background |
| `navy-900` | `#0B1729` | Deepest surface, dark AI panels |
| `indigo-50` | `#EEF0FE` | Light AI surface |
| `indigo-100` | `#E0E3FC` | AI badge background |
| `indigo-200` | `#C4C9F9` | AI border |
| `indigo-300` | `#9AA2F2` | AI accent on dark |
| `indigo-400` | `#7B84EC` | AI text on dark / focus on AI |
| `indigo-500` | `#5B62E3` | Sidebar active bar (only non-AI indigo exception) |
| `indigo-600` | `#4A4FD1` | **AI primary** (Generate / Ask / Extract buttons) |
| `indigo-700` | `#3B3FAC` | AI hover |
| `violet-500` | `#8B5CF6` | Charts only, sparing — not UI chrome |
| `amber-50` | `#FFF8EB` | Opportunity / recovery background |
| `amber-100` | `#FEEFC7` | Opportunity fill |
| `amber-300` | `#FCD34D` | Chart fill |
| `amber-500` | `#F59E0B` | Chart series |
| `amber-600` | `#D97706` | **Opportunity / attention / recovery high** |
| `amber-700` | `#B45309` | Text on amber-50; recommended-action label |
| `green-50` | `#ECFDF5` | Positive background |
| `green-100` | `#D1FAE5` | Positive fill |
| `green-600` | `#059669` | **Positive / approved** |
| `green-700` | `#047857` | Text on green-50 |
| `red-50` | `#FEF2F2` | Risk background |
| `red-100` | `#FEE2E2` | Risk fill |
| `red-600` | `#DC2626` | **Risk / high risk band** |
| `red-700` | `#B91C1C` | Text on red-50 |
| `neutral-0` | `#FFFFFF` | Cards |
| `neutral-50` | `#F7F9FC` | App background |
| `neutral-100` | `#EEF2F7` | Sunken surfaces, table headers |
| `neutral-200` | `#E2E8F0` | Default border |
| `neutral-300` | `#CBD5E1` | Strong border |
| `neutral-400` | `#94A3B8` | Muted text, placeholder |
| `neutral-500` | `#64748B` | Secondary text |
| `neutral-600` | `#475569` | Body on tint |
| `neutral-700` | `#334155` | Strong body |
| `neutral-900` | `#0F172A` | Primary text |

Neutrals are blue-tinted so white cards, navy chrome, and body text read as one family.

### 2.2 Semantic tokens

| Token | Value | Meaning |
|---|---|---|
| `bg-app` | `neutral-50` | App background |
| `surface` | `neutral-0` | Card, panel |
| `surface-sunken` | `neutral-100` | Table headers, inset |
| `surface-selected` | `navy-50` | Selected row |
| `surface-ai` | `navy-900` | Dark AI panel |
| `surface-ai-subtle` | `indigo-50` | Light AI region (drafts, long answers) |
| `border-default` | `neutral-200` | Standard border |
| `border-strong` | `neutral-300` | Emphasis |
| `border-ai` | `indigo-200` | AI border |
| `text-primary` | `neutral-900` | Headings, body |
| `text-secondary` | `neutral-500` | Labels, metadata |
| `text-muted` | `neutral-400` | Disabled, timestamps |
| `text-inverse` | `neutral-0` | On navy |
| `text-on-ai` | `#E8EBF5` | Body on `surface-ai` |
| `text-on-ai-muted` | `navy-300` | Secondary on `surface-ai` |
| `status-opportunity` | `amber-600` | Recoverable, attention |
| `status-positive` | `green-600` | Healthy, approved |
| `status-risk` | `red-600` | At risk, hard failure |
| `status-ai` | `indigo-600` | AI-generated |
| `status-neutral` | `neutral-500` | Information / rejected draft |
| `interactive` | `navy-600` | Primary action, link |
| `interactive-hover` | `navy-700` | Hover |
| `focus-ring` | `navy-400` | Focus on light |
| `focus-ring-ai` | `indigo-400` | Focus on dark AI |

### 2.3 CSS variables (implement once in `frontend`)

```css
:root {
  --color-navy-600: #1E3A66;
  --color-navy-800: #11223D;
  --color-navy-900: #0B1729;
  --color-indigo-600: #4A4FD1;
  --color-amber-600: #D97706;
  --color-green-600: #059669;
  --color-red-600: #DC2626;
  --color-bg-app: #F7F9FC;
  --color-surface: #FFFFFF;
  --color-border: #E2E8F0;
  --color-text: #0F172A;
  --color-text-secondary: #64748B;
}
```

Extend Tailwind with the full scales in §2.1. Prefer `bg-navy-600`, `text-status-risk`, etc.

### 2.4 Reserved color rules (all features)

1. **Indigo / violet = AI only** (except 3px sidebar active bar = `indigo-500`).
2. **Amber** = recoverable / needs attention / recommended action — not branding.
3. **Green** = approved / healthy / success — not “good lead”.
4. **Red** = at risk / failure — not “bad lead”; rejected drafts stay **neutral**.
5. **Navy** = structure and primary chrome — not status.
6. Color never carries meaning alone — always a text label.

### 2.5 Feature → color usage (same palette)

| Feature | Primary chrome | Status emphasis | AI surfaces |
|---|---|---|---|
| Shell / Briefing | navy sidebar + primary | metric cards neutral | dark `AiPanel` for briefing note |
| F1 Recovery | navy tables/links | high recovery = amber band | re-engagement draft = light AI + ApprovalBar |
| F2 Risk | navy | high risk = red; medium = amber | explanation = dark or light AiPanel |
| F3 Meeting | navy | confirmed=green outline; unconfirmed=amber; unknown=neutral | extraction = light AI |
| F4 Blocker | navy | answered=green outline; partial=amber; insufficient=navy tint notice | answer = light AI + citations |
| F5 Drafts | navy | draft=neutral; approved=green | proposal/follow-up = light AI |
| F6 Handoff | navy | won=green pill; checklist progress green | handoff draft = light AI |

### 2.6 Band colors

| Score type | Band | Treatment |
|---|---|---|
| Recovery | `high` | `amber-600` text, `amber-50` fill |
| Recovery | `medium` | `navy-500` text, `navy-50` fill, outlined |
| Recovery | `low` | `neutral-500` text, `surface-sunken`, outlined |
| Risk | `high` | `red-600` text, `red-50` fill |
| Risk | `medium` | `amber-600` text, `amber-50` fill, outlined |
| Risk | `low` | `neutral-500` text, `surface-sunken`, outlined |

### 2.7 Layer colors

| Layer | Label | Treatment |
|---|---|---|
| `fact` | FACT | `neutral-600` on `surface-sunken` |
| `interpretation` | AI INTERPRETATION | `indigo-600` on `indigo-50`, indigo left rule |
| `recommended_action` | RECOMMENDED ACTION | `amber-700` on `amber-50`, amber left rule |

### 2.8 Tailwind theme reference

```js
// Transcribe at implementation — do not invent alternate hex values.
theme: { extend: { colors: {
  navy:   { 50:'#EEF2F8',100:'#D8E1EF',200:'#B3C3DD',300:'#7F97BE',400:'#4E6B9B',
            500:'#2F4E7E',600:'#1E3A66',700:'#172E52',800:'#11223D',900:'#0B1729' },
  indigo: { 50:'#EEF0FE',100:'#E0E3FC',200:'#C4C9F9',300:'#9AA2F2',400:'#7B84EC',
            500:'#5B62E3',600:'#4A4FD1',700:'#3B3FAC' },
  amber:  { 50:'#FFF8EB',100:'#FEEFC7',300:'#FCD34D',500:'#F59E0B',600:'#D97706',700:'#B45309' },
  green:  { 50:'#ECFDF5',100:'#D1FAE5',600:'#059669',700:'#047857' },
  red:    { 50:'#FEF2F2',100:'#FEE2E2',600:'#DC2626',700:'#B91C1C' },
  violet: { 500:'#8B5CF6' },
  neutral:{ 0:'#FFFFFF',50:'#F7F9FC',100:'#EEF2F7',200:'#E2E8F0',300:'#CBD5E1',
            400:'#94A3B8',500:'#64748B',600:'#475569',700:'#334155',900:'#0F172A' },
  surface:{ DEFAULT:'#FFFFFF', sunken:'#EEF2F7', selected:'#EEF2F8', ai:'#0B1729', 'ai-subtle':'#EEF0FE' },
  status: { opportunity:'#D97706', positive:'#059669', risk:'#DC2626', ai:'#4A4FD1', neutral:'#64748B' },
}}}
```

---

## 3. Typography

**Inter** via `@fontsource/inter`. Fallback: `Inter, -apple-system, "Segoe UI", Roboto, sans-serif`.
`tabular-nums` for money and scores. Ids (`ACC-0181`, `KB-OFF-02`) use system monospace.
Weights: 400, 500, 600, 700 only.

| Token | Size / line | Weight | Use |
|---|---|---|---|
| `text-display` | 30 / 36 | 600 | Dashboard title only |
| `text-h1` | 24 / 32 | 600 | Page titles |
| `text-h2` | 20 / 28 | 600 | Section headings |
| `text-h3` | 16 / 24 | 600 | Card titles |
| `text-body-lg` | 16 / 24 | 400 | AI explanations, answers, drafts |
| `text-body` | 14 / 20 | 400 | Default |
| `text-body-sm` | 13 / 18 | 400 | Tables, snippets |
| `text-caption` | 12 / 16 | 400 | Metadata |
| `text-label` | 11 / 16 | 600 | Uppercase labels (`tracking 0.06em`) |
| `text-metric` | 28 / 32 | 600 | Dashboard metrics |
| `text-score` | 44 / 48 | 700 | Score value |

---

## 4. Spacing, radius, shadow, motion

- Spacing steps: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64 px.
- Sidebar 260px (72px collapsed), header 64px, content max 1440px, page pad 32px, card pad 24px,
  gutter 24px, evidence drawer 480px, modal 560px (800 wide).
- Radius: `sm` 4, `md` 6, `lg` 8, `xl` 12, `full` pills. Nothing > 12 except pills.
- Shadows: `xs`–`lg` with `neutral-900` low alpha only. No colored glow.
- Motion: 120 / 180 / 240 ms, `ease-out`. Honor `prefers-reduced-motion`.

---

## 5. Icons (`lucide-react`)

20px nav, 16px inline, stroke 1.75.

| Concept | Icon |
|---|---|
| Briefing | `LayoutDashboard` |
| F1 Recovery | `RotateCcw` |
| F2 Risk | `ShieldAlert` |
| Account / deal | `Briefcase` |
| F3 Meeting | `Mic` / `FileText` |
| F4 Blocker | `HelpCircle` |
| F5 Draft | `FilePen` |
| F6 Handoff | `PackageCheck` |
| Knowledge | `BookOpen` |
| Data status | `Database` |
| AI | `Sparkles` (AI only) |
| Evidence | `Quote` |
| Approved | `CheckCircle2` |
| Rejected | `XCircle` (neutral) |

---

## 6. Core components

**Buttons:** Primary = `navy-600`; Secondary = white + `border-strong`; **AI action** = `indigo-600`
+ `Sparkles` (only indigo button); Destructive = `red-600` outline + confirm; Ghost = tertiary.
No "Send". Labels: "Generate explanation", "Approve draft", "Mark as won", "Save to CRM".

**Tables / cards / badges:** as prior Premium Hybrid rules (`surface`, `rounded-lg`, band pills
always include text).

**Confirm dialog:** Mark won, Reopen, Save meeting. Always state what does **not** happen
("This does not mean revenue was recovered.").

---

## 7. AI components

Keep: `AiLabel`, `AiPanel` (dark + light), `ClaimBlock`, `EvidenceChip`,
`InsufficientEvidenceNotice` (navy tint, not red), `AiUnavailableNotice`, `ApprovalBar`,
`DraftNotice`.

---

## 8. Domain components

| Component | Notes for `crm_master` MVP |
|---|---|
| `FictionalBadge` | Always visible: "Fictional demo data" |
| `IllustrativeBadge` | On rows that use a real institution name as an illustrative target |
| `PublicSourceTag` | When `signal_source_url` / citation URL is stored |
| `BandPill` / `ScoreDisplay` / `FactorBreakdown` | F1/F2 |
| `AccountRow` | Replaces DealRow naming: `account_name`, `opportunity_name`, `deal_value`, stage, status, score |
| `StatusPill` | `open` navy outline; `won` green; `lost`/`inactive`/`stalled`/`none` neutral with clear label |
| `SignalCard` | F1 public/synthetic signals |
| `TimelineItem` | From `activity_history` |
| `WorkflowStepper` | Find→Assess→Understand→Resolve→Draft→Handoff |
| `ExtractionTable` | F3 statuses confirmed/unconfirmed/unknown |
| `BlockerAnswerCard` | F4 |
| `FileDropzone` | txt/docx/pdf + optional audio; paste fallback |
| `MetricCard` | At-risk card must say "At-risk value, not lost revenue" |
| `DataStatusCard` | Shows DB row count / as-of from `GET /data/status` (not CSV import) |

---

## 9. Evidence drawer

Right 480px drawer. Snippet + context; public URLs only when stored. Escape closes; focus returns
to chip.

---

## 10. Navigation and routes

Sidebar: `navy-800`, active item `navy-900` + 3px `indigo-500` bar. Header 64px with
`FictionalBadge`.

| Route | Page | Feature |
|---|---|---|
| `/login` | Clerk sign-in | Auth |
| `/` | Today's briefing / dashboard | Shell |
| `/recovery` | Lost lead recovery list | F1 |
| `/recovery/:accountId` | Recovery detail + draft | F1 |
| `/risk` | Risk prioritizer list | F2 |
| `/risk/:accountId` | Risk detail | F2 |
| `/accounts/:accountId` | Account overview (shared) | All |
| `/accounts/:accountId/meetings` | Meeting upload + extractions | F3 |
| `/accounts/:accountId/blockers` | Blocker Q&A | F4 |
| `/accounts/:accountId/drafts` | Follow-up / proposal | F5 |
| `/accounts/:accountId/handoff` | Handoff | F6 |
| `/knowledge` | KB index (optional) | F4 |
| `/data` | Data status (read-only counts) | Ops |
| `/signal-scout` | Signal Scout — targets / Scan now | F7 stretch |
| `/signal-scout/:targetId` | Target card, signals, potential opportunities | F7 stretch |

Parallel folders may mirror these under `frontend/src/pages/f1_recovery`, etc., but routes stay
unified so the product looks one.

---

## 11. Screen requirements (MVP)

### Briefing `/`
Metric cards: open pipeline, at-risk (with note), recovery eligible count, high-risk count.
Briefing list (rule-ordered) with navy links. Optional Recharts using navy/amber/indigo series only.

### F1 Recovery
Table of eligible/review accounts. Detail: lost reason, inactivity, PUBLIC_VERIFIED signal with
`PublicSourceTag`, claims, re-engagement draft + `ApprovalBar`. Reopen confirm. Email-sent updates
activity only.

### F2 Risk
Sortable by `revenue_risk_score`. Detail: `ScoreDisplay`, factors, evidence, recommended action.

### F3 Meetings
Dropzone → match account (ACC-0181 demo) → extraction table → Save to CRM (append
`uploaded_meetings`). Show pre-generated meeting and uploads separately.

### F4 Blockers
Question input + AI Ask. Answer card with citations. Insufficient-evidence notice. Approve/reject.

### F5 Drafts
Follow-up and proposal outline on light AI surface. Completeness / open questions. ApprovalBar.

### F6 Handoff
Only when won (or after Mark won confirm). Summary, requirements, stakeholders, risks, checklist.
Approve handoff review state.

### Data `/data`
Read-only: schema, row count, as-of date, KB files present. **No CSV import/reset buttons** unless
re-approved.

---

## 12. States

Every list/detail: loading skeleton, empty, error, populated.  
AI: generating, unavailable, invalid output.  
Drafts: draft / approved / rejected.  
Never blank the page on `insufficient_evidence`.

---

## 13. Accessibility

- Contrast: body on `neutral-50`/`surface` meets WCAG AA; AI dark panel uses `text-on-ai`.
- Visible focus rings (`focus-ring` / `focus-ring-ai`).
- Keyboard: full demo path without mouse; drawer focus trap.
- Meaning not by color alone.
- Desktop-first; do not hide scores, evidence, or AI labels at 1024px.

---

## 14. Copy rules

May: "may be worth reviewing", "recommended action", "at risk", "draft", "illustrative".  
Must not: "will close", "is recovered", "guaranteed", "Send", claiming a real institution is a
customer.

---

## Document history

| Date | Change |
|---|---|
| 2026-11-04 | Locked Premium Hybrid colors for all features; routes/screens aligned to `crm_master` |
