import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { apiRequest } from '../../api/client'
import { FictionalBadge } from '../../components/FictionalBadge'
import {
  clearGmailToken,
  connectGmail,
  getValidGmailAccessToken,
  isGmailConfigured,
  peekGmailAccessToken,
} from '../../lib/gmailAuth'

type RecoveryDetail = {
  account_id: string
  account_name: string
  opportunity_name: string | null
  deal_status: string
  deal_value: number
  currency: string
  contact_name: string | null
  contact_email: string | null
  account_owner: string | null
  lost_reason: string | null
  inactivity_days: number | null
  last_activity_date: string | null
  recovery_eligibility: string | null
  signal: {
    title: string | null
    description: string | null
    classification: string | null
    source_url: string | null
  }
  explanation: {
    facts: Array<{ layer: string; text: string }>
    interpretation: { text: string }
    recommended_action: { text: string }
  }
  draft: { subject: string | null; body: string | null; state: string }
  gmail_thread: GmailThread | null
  as_of_date: string
}

type GmailThread = {
  source: string
  mailbox?: string
  scanned_count?: number
  match_mode?: string
  notice?: string
  new_messages: GmailMsg[]
  previous_messages: GmailMsg[]
}

type GmailMsg = {
  gmail_message_id: string
  date: string
  from: string
  to: string
  subject: string
  snippet: string
  body?: string
}

type CrmPreview = {
  summary: string
  proposed_activity: { description: string; date: string; type: string }
  field_updates: Record<string, string | number>
  will_not_change: string[]
}

function money(n: number, currency: string) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency || 'USD',
    maximumFractionDigits: 0,
  }).format(n)
}

export function RecoveryDetailPage() {
  const { accountId = '' } = useParams()
  const qc = useQueryClient()
  const [subject, setSubject] = useState<string | null>(null)
  const [body, setBody] = useState<string | null>(null)
  const [preview, setPreview] = useState<CrmPreview | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [gmailConnected, setGmailConnected] = useState(() => Boolean(peekGmailAccessToken()))
  const [syncedThread, setSyncedThread] = useState<GmailThread | null>(null)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['recovery', accountId],
    queryFn: () => apiRequest<RecoveryDetail>(`/api/v1/accounts/${accountId}/recovery`),
    enabled: !!accountId,
  })

  const draftSubject = subject ?? data?.draft.subject ?? ''
  const draftBody = body ?? data?.draft.body ?? ''

  const generate = useMutation({
    mutationFn: () =>
      apiRequest<{ subject: string; body: string; source?: string }>(
        `/api/v1/accounts/${accountId}/drafts/reengagement`,
        { method: 'POST' },
      ),
    onSuccess: (d) => {
      setSubject(d.subject)
      setBody(d.body)
      void qc.invalidateQueries({ queryKey: ['recovery', accountId] })
      const via =
        d.source === 'azure_openai'
          ? 'Azure OpenAI'
          : d.source === 'sample'
            ? 'sample fallback'
            : 'template'
      setToast(`Draft generated via ${via} (not sent).`)
    },
  })

  const saveDraft = useMutation({
    mutationFn: () =>
      apiRequest(`/api/v1/accounts/${accountId}/drafts/reengagement`, {
        method: 'PATCH',
        body: JSON.stringify({ subject: draftSubject, body: draftBody }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['recovery', accountId] })
      setToast('Draft saved.')
    },
  })

  const connectGmailAccount = useMutation({
    mutationFn: () => connectGmail(),
    onSuccess: () => {
      setGmailConnected(true)
      setToast('Gmail connected (readonly). Click Sync Emails to load this contact’s thread.')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Gmail connect failed'),
  })

  const syncGmail = useMutation({
    mutationFn: async () => {
      let accessToken: string | undefined
      if (isGmailConfigured()) {
        try {
          accessToken = await getValidGmailAccessToken()
          setGmailConnected(true)
        } catch {
          // Fall through — backend may return fixtures when DEMO_GMAIL_FIXTURES=true.
          accessToken = undefined
        }
      }
      return apiRequest<GmailThread>(`/api/v1/accounts/${accountId}/gmail/sync`, {
        method: 'POST',
        body: JSON.stringify({ access_token: accessToken }),
      })
    },
    onSuccess: (thread) => {
      setSyncedThread(thread)
      void refetch()
      if (thread.source === 'gmail') {
        const count = thread.new_messages.length + thread.previous_messages.length
        setToast(
          thread.notice ||
            `Synced ${count} messages` +
              (thread.mailbox ? ` from ${thread.mailbox}` : '') +
              '. Nothing sent.',
        )
      } else {
        setToast('Gmail thread loaded from demo fixtures (connect Gmail for live mail).')
      }
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Gmail sync failed'),
  })

  const loadPreview = useMutation({
    mutationFn: () => apiRequest<CrmPreview>(`/api/v1/accounts/${accountId}/crm-log/preview`),
    onSuccess: setPreview,
  })

  const confirmLog = useMutation({
    mutationFn: () =>
      apiRequest(`/api/v1/accounts/${accountId}/crm-log/confirm`, {
        method: 'POST',
        body: JSON.stringify({ confirm: true, source: 'draft' }),
      }),
    onSuccess: () => {
      setPreview(null)
      void refetch()
      void qc.invalidateQueries({ queryKey: ['recovery'] })
      setToast('CRM updated. Deal still not marked recovered.')
    },
  })

  const reopen = useMutation({
    mutationFn: () =>
      apiRequest(`/api/v1/accounts/${accountId}/reopen`, {
        method: 'POST',
        body: JSON.stringify({ confirm: true }),
      }),
    onSuccess: () => {
      void refetch()
      void qc.invalidateQueries({ queryKey: ['recovery'] })
      setToast('Opportunity reopened to open — not recovered revenue.')
    },
  })

  if (isLoading) return <p className="text-neutral-500">Loading…</p>
  if (error || !data) {
    return <p className="text-red-600">{error instanceof Error ? error.message : 'Not found'}</p>
  }

  const thread = syncedThread ?? data.gmail_thread

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/recovery" className="text-sm text-navy-600 hover:underline">
            ← Lead Recovery
          </Link>
          <h2 className="mt-1 text-2xl font-semibold text-neutral-900">{data.account_name}</h2>
          <p className="text-sm text-neutral-500">
            {data.opportunity_name} · {data.account_id} · as of {data.as_of_date}
          </p>
        </div>
        <FictionalBadge />
      </div>

      {toast && (
        <div className="rounded-md border border-green-600/20 bg-green-50 px-3 py-2 text-sm text-green-700">
          {toast}
        </div>
      )}

      <section className="grid gap-4 rounded-lg border border-neutral-200 bg-white p-4 md:grid-cols-3">
        <div>
          <p className="text-xs text-neutral-500 uppercase">Status</p>
          <p className="mt-1 font-medium capitalize">{data.deal_status}</p>
        </div>
        <div>
          <p className="text-xs text-neutral-500 uppercase">Value</p>
          <p className="mt-1 font-medium text-navy-600">{money(data.deal_value, data.currency)}</p>
        </div>
        <div>
          <p className="text-xs text-neutral-500 uppercase">Inactivity</p>
          <p className="mt-1 font-medium">{data.inactivity_days ?? '—'} days</p>
        </div>
        <div>
          <p className="text-xs text-neutral-500 uppercase">Contact</p>
          <p className="mt-1 font-medium">{data.contact_name || '—'}</p>
          <p className="text-xs text-neutral-500">{data.contact_email}</p>
        </div>
        <div>
          <p className="text-xs text-neutral-500 uppercase">Owner</p>
          <p className="mt-1 font-medium">{data.account_owner || '—'}</p>
        </div>
        <div>
          <p className="text-xs text-neutral-500 uppercase">Eligibility</p>
          <p className="mt-1 font-medium capitalize text-amber-700">{data.recovery_eligibility}</p>
        </div>
      </section>

      <section className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-4">
        <p className="text-xs font-semibold tracking-wide text-indigo-700 uppercase">Why this account</p>
        <div className="mt-3 space-y-3">
          {data.explanation.facts.map((f, i) => (
            <div key={i}>
              <p className="text-xs font-medium text-neutral-500">FACT</p>
              <p className="text-sm text-neutral-800">{f.text}</p>
            </div>
          ))}
          <div>
            <p className="text-xs font-medium text-indigo-700">AI INTERPRETATION</p>
            <p className="text-sm text-neutral-800">{data.explanation.interpretation.text}</p>
          </div>
          <div className="rounded-md border border-amber-600/20 bg-amber-50 p-3">
            <p className="text-xs font-medium text-amber-700">RECOMMENDED ACTION</p>
            <p className="text-sm text-amber-900">{data.explanation.recommended_action.text}</p>
          </div>
        </div>
      </section>

      {data.signal.title && (
        <section className="rounded-lg border border-neutral-200 bg-white p-4">
          <p className="text-xs font-semibold text-neutral-500 uppercase">Signal</p>
          <p className="mt-1 font-medium text-neutral-900">{data.signal.title}</p>
          <p className="mt-1 text-sm text-neutral-600">{data.signal.description}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
              {data.signal.classification}
            </span>
            {data.signal.source_url && (
              <a
                href={data.signal.source_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-navy-600 hover:underline"
              >
                Open public source
              </a>
            )}
          </div>
        </section>
      )}

      <section className="rounded-lg border border-neutral-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="font-semibold text-neutral-900">Gmail thread</p>
            <p className="text-xs text-neutral-500">
              Read-only sync matched to {data.contact_email || 'contact_email'}. Does not send mail.
              {gmailConnected ? ' · Gmail connected' : ''}
              {!isGmailConfigured() ? ' · Set VITE_GOOGLE_CLIENT_ID for live sync' : ''}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {isGmailConfigured() && (
              <button
                type="button"
                onClick={() => connectGmailAccount.mutate()}
                disabled={connectGmailAccount.isPending || syncGmail.isPending}
                className="rounded-md border border-navy-600 bg-navy-50 px-3 py-2 text-sm font-medium text-navy-700 disabled:opacity-50"
              >
                {connectGmailAccount.isPending
                  ? 'Connecting…'
                  : gmailConnected
                    ? 'Reconnect Gmail'
                    : 'Connect Gmail'}
              </button>
            )}
            {gmailConnected && (
              <button
                type="button"
                onClick={() => {
                  clearGmailToken()
                  setGmailConnected(false)
                  setToast('Gmail disconnected for this browser session.')
                }}
                className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-700"
              >
                Disconnect
              </button>
            )}
            <button
              type="button"
              onClick={() => syncGmail.mutate()}
              disabled={syncGmail.isPending || !data.contact_email}
              title={!data.contact_email ? 'No contact_email on this account' : undefined}
              className="rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white hover:bg-navy-700 disabled:opacity-50"
            >
              {syncGmail.isPending ? 'Syncing…' : 'Sync Emails'}
            </button>
          </div>
        </div>
        {thread?.source === 'fixture' && (
          <p className="mt-2 text-xs font-medium text-amber-700">Demo thread (fixture)</p>
        )}
        {thread?.source === 'gmail' && (
          <p className="mt-2 text-xs font-medium text-green-700">
            Live Gmail · scanned {thread.scanned_count ?? 0}
            {thread.mailbox ? ` · ${thread.mailbox}` : ''}
            {thread.match_mode === 'recent_inbox' ? ' · recent inbox fallback' : ''}
          </p>
        )}
        {thread?.notice && (
          <p className="mt-2 text-xs text-amber-800">{thread.notice}</p>
        )}
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <MessageList title="New" messages={thread?.new_messages ?? []} />
          <MessageList title="Previous" messages={thread?.previous_messages ?? []} />
        </div>
      </section>

      <section className="rounded-lg border border-indigo-200 bg-indigo-50/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="font-semibold text-neutral-900">Re-engagement draft</p>
            <p className="text-xs text-neutral-500">
              State: {data.draft.state} · Approval does not send email.
            </p>
          </div>
          <button
            type="button"
            onClick={() => generate.mutate()}
            className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            {generate.isPending ? 'Generating…' : 'Generate / load sample'}
          </button>
        </div>
        <label className="mt-4 block text-xs font-medium text-neutral-500">Subject</label>
        <input
          className="mt-1 w-full rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm"
          value={draftSubject}
          onChange={(e) => setSubject(e.target.value)}
        />
        <label className="mt-3 block text-xs font-medium text-neutral-500">Body</label>
        <textarea
          className="mt-1 min-h-40 w-full rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm"
          value={draftBody}
          onChange={(e) => setBody(e.target.value)}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => saveDraft.mutate()}
            className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-navy-700"
          >
            Save edits
          </button>
          <button
            type="button"
            onClick={() => loadPreview.mutate()}
            className="rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white hover:bg-navy-700"
          >
            Log to CRM
          </button>
          <button
            type="button"
            onClick={() => {
              if (window.confirm('Reopen this opportunity? This does not mean revenue was recovered.')) {
                reopen.mutate()
              }
            }}
            className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-neutral-700"
          >
            Reopen opportunity
          </button>
        </div>
      </section>

      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/40 p-4">
          <div className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-lg bg-white p-5 shadow-xl">
            <h3 className="text-lg font-semibold">Review CRM updates before logging</h3>
            <p className="mt-2 text-sm text-neutral-600">{preview.summary}</p>
            <p className="mt-3 text-sm font-medium">Email to log</p>
            <p className="text-sm text-neutral-700">{preview.proposed_activity.description}</p>
            <p className="mt-3 text-sm font-medium">Will update</p>
            <ul className="mt-1 list-inside list-disc text-sm text-neutral-700">
              {Object.entries(preview.field_updates).map(([k, v]) => (
                <li key={k}>
                  {k}: {String(v)}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-sm font-medium">Will not change</p>
            <ul className="mt-1 list-inside list-disc text-sm text-neutral-600">
              {preview.will_not_change.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="rounded-md px-3 py-2 text-sm text-neutral-600"
                onClick={() => setPreview(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white"
                onClick={() => confirmLog.mutate()}
              >
                {confirmLog.isPending ? 'Saving…' : 'Confirm sync'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MessageBody({ snippet, body }: { snippet: string; body?: string }) {
  // Prefer full body; fall back to snippet only if body was not returned.
  const full = (body && body.trim().length > (snippet || '').trim().length ? body : body || snippet || '').trim()
  const [expanded, setExpanded] = useState(true)
  const previewLimit = 220
  const needsMore = full.length > previewLimit
  const shown = expanded || !needsMore ? full : `${full.slice(0, previewLimit).trimEnd()}…`

  return (
    <div className="mt-1">
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-neutral-700">{shown}</p>
      {needsMore && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-1 text-xs font-medium text-navy-600 hover:underline"
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}
    </div>
  )
}

function MessageList({ title, messages }: { title: string; messages: GmailMsg[] }) {
  return (
    <div>
      <p className="text-xs font-semibold tracking-wide text-neutral-500 uppercase">{title}</p>
      {messages.length === 0 ? (
        <p className="mt-2 text-sm text-neutral-400">No messages</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {messages.map((m) => (
            <li key={m.gmail_message_id} className="rounded-md border border-neutral-200 p-3">
              <p className="text-sm font-medium text-neutral-900">{m.subject}</p>
              <p className="text-xs text-neutral-500">
                {m.from} → {m.to} · {new Date(m.date).toLocaleDateString()}
              </p>
              <MessageBody snippet={m.snippet} body={m.body} />
              <p className="mt-1 text-[11px] text-neutral-400">Gmail · {m.gmail_message_id}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
