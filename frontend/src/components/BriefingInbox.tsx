import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Mail, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { apiRequest } from '../api/client'
import { env } from '../lib/env'
import { clearGmailAccessToken, requestGmailAccessToken } from '../lib/gmailAuth'

type InboxItem = {
  gmail_message_id: string
  thread_id?: string
  date: string
  from: string
  to: string
  subject: string
  snippet: string
  direction?: string
  already_in_crm?: boolean
  crm_match: null | {
    account_id: string
    account_name: string
    contact_email?: string
    deal_status?: string
    match_type?: string
  }
  proposed_crm_update?: {
    interpretation?: string
    status_note?: string
    current?: Record<string, string | number | null | undefined>
    field_updates?: Record<string, string | number>
  }
}

type InboxPayload = {
  mailbox_email?: string | null
  synced_at?: string | null
  total_scanned?: number
  total_listed?: number
  pending_approval_count?: number
  skipped_approved?: number
  skipped_no_crm_match?: number
  skipped_non_sales?: number
  items: InboxItem[]
  notice?: string
}

type InboxPreview = {
  summary: string
  interpretation?: string
  status_note?: string
  account_id: string
  account_name: string
  match_type?: string
  email: { subject?: string; snippet?: string; from?: string; direction?: string }
  current?: Record<string, string | number | null | undefined>
  field_updates: Record<string, string | number>
  will_not_change: string[]
  proposed_activity: { description: string }
}

function formatWhen(iso?: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16)
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function BriefingInbox() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [preview, setPreview] = useState<InboxPreview | null>(null)
  const [previewId, setPreviewId] = useState<string | null>(null)

  const statusQ = useQuery({
    queryKey: ['gmail-status'],
    queryFn: () =>
      apiRequest<{
        connected: boolean
        mailbox_email?: string
        pending_crm_approvals?: number
        last_synced_at?: string
        login_hint?: string
      }>('/api/v1/gmail/status'),
    staleTime: 15_000,
  })

  const inboxQ = useQuery({
    queryKey: ['gmail-inbox'],
    queryFn: () => apiRequest<InboxPayload>('/api/v1/gmail/inbox'),
    enabled: open,
  })

  const refresh = useMutation({
    mutationFn: async () => {
      const run = async () => {
        const access_token = await requestGmailAccessToken()
        return apiRequest<InboxPayload>('/api/v1/gmail/inbox/refresh', {
          method: 'POST',
          body: JSON.stringify({ access_token }),
        })
      }
      try {
        return await run()
      } catch (e) {
        // Token expired/revoked → clear cache and consent once more
        const msg = e instanceof Error ? e.message : ''
        if (/gmail|401|auth|token|unauthorized/i.test(msg)) {
          clearGmailAccessToken()
          return await run()
        }
        throw e
      }
    },
    onSuccess: (data) => {
      void qc.setQueryData(['gmail-inbox'], data)
      void qc.invalidateQueries({ queryKey: ['gmail-status'] })
      setOpen(true)
      const pending = data.pending_approval_count ?? data.items.length
      setToast(
        pending > 0
          ? `${pending} sales/lead email(s) need CRM approve · skipped already-logged ${data.skipped_approved ?? 0}`
          : `No new sales/lead emails pending · scanned ${data.total_scanned ?? 0} · already logged ${data.skipped_approved ?? 0}`,
      )
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Inbox refresh failed'),
  })

  const loadPreview = useMutation({
    mutationFn: (id: string) =>
      apiRequest<InboxPreview>(`/api/v1/gmail/inbox/${encodeURIComponent(id)}/preview`),
    onSuccess: (p, id) => {
      setPreview(p)
      setPreviewId(id)
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Preview failed'),
  })

  const approve = useMutation({
    mutationFn: (id: string) =>
      apiRequest(`/api/v1/gmail/inbox/${encodeURIComponent(id)}/approve`, {
        method: 'POST',
        body: JSON.stringify({ confirm: true }),
      }),
    onSuccess: async () => {
      setPreview(null)
      setPreviewId(null)
      // Drop from UI immediately; re-fetch cache (approved ids stay hidden on next sync)
      const cached = await apiRequest<InboxPayload>('/api/v1/gmail/inbox')
      void qc.setQueryData(['gmail-inbox'], cached)
      void qc.invalidateQueries({ queryKey: ['gmail-status'] })
      void qc.invalidateQueries({ queryKey: ['dashboard'] })
      void qc.invalidateQueries({ queryKey: ['recovery'] })
      setToast('Approved into CRM · removed from inbox queue. Re-sync will not show it again.')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Approve failed'),
  })

  const pending =
    statusQ.data?.pending_crm_approvals ??
    inboxQ.data?.pending_approval_count ??
    0
  // Only pending CRM-matched sales leads (old cache may still have null matches)
  const items = (inboxQ.data?.items ?? []).filter(
    (i): i is InboxItem & { crm_match: NonNullable<InboxItem['crm_match']> } =>
      Boolean(i.crm_match?.account_id) && !i.already_in_crm,
  )

  return (
    <section className="rounded-xl border border-navy-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold tracking-wide text-neutral-500 uppercase">
            Sales inbox leads
          </p>
          <p className="mt-0.5 text-sm text-neutral-600">
            Live Gmail only · sales/lead + CRM match · approve once, then hidden
          </p>
          {statusQ.data?.mailbox_email && (
            <p className="mt-1 text-[11px] text-neutral-400">
              Connected as {statusQ.data.mailbox_email}
              {statusQ.data.last_synced_at
                ? ` · last sync ${formatWhen(statusQ.data.last_synced_at)}`
                : ''}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-navy-700"
          >
            {open ? 'Hide inbox' : pending > 0 ? `Review inbox (${pending})` : 'Open inbox'}
          </button>
          <button
            type="button"
            disabled={!env.googleClientId || refresh.isPending}
            onClick={() => refresh.mutate()}
            className="inline-flex items-center gap-1.5 rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white hover:bg-navy-700 disabled:opacity-50"
          >
            <RefreshCw className={`size-3.5 ${refresh.isPending ? 'animate-spin' : ''}`} />
            {refresh.isPending ? 'Syncing Gmail…' : 'Sync Gmail inbox'}
          </button>
        </div>
      </div>

      {!env.googleClientId && (
        <p className="mt-3 text-sm text-amber-700">
          Set VITE_GOOGLE_CLIENT_ID to enable live Gmail sync.
        </p>
      )}

      {toast && (
        <p className="mt-3 rounded-md border border-green-600/20 bg-green-50 px-3 py-2 text-sm text-green-800">
          {toast}
        </p>
      )}

      {open && (
        <div className="mt-4 space-y-3">
          <p className="text-xs text-neutral-500">
            {inboxQ.data?.notice ||
              'Sync pulls Inbox + Sent. Only unmatched sales/lead emails tied to CRM appear here.'}
          </p>

          {items.length === 0 ? (
            <p className="text-sm text-neutral-400">
              No pending sales/lead emails. Send or receive a CRM-related message, then Sync again.
            </p>
          ) : (
            <ul className="space-y-2">
              {items.map((item) => (
                <li
                  key={item.gmail_message_id}
                  className="rounded-lg border border-neutral-200 bg-neutral-50/80 p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 text-[11px]">
                        <span className="inline-flex items-center gap-1 rounded bg-navy-100 px-1.5 py-0.5 font-medium text-navy-800">
                          <Mail className="size-3" />
                          {item.direction || 'email'}
                        </span>
                        <span className="rounded bg-amber-50 px-1.5 py-0.5 font-medium text-amber-800">
                          Pending approve
                        </span>
                        <span className="text-neutral-500">{formatWhen(item.date)}</span>
                      </div>
                      <p className="mt-1 text-sm font-medium text-neutral-900">{item.subject}</p>
                      <p className="text-xs text-neutral-500">
                        {item.from} → {item.to}
                      </p>
                      <p className="mt-1 text-sm text-neutral-600">{item.snippet}</p>
                      <p className="mt-2 text-xs text-navy-700">
                        Matched{' '}
                        <Link
                          className="font-semibold hover:underline"
                          to={`/recovery/${item.crm_match.account_id}`}
                        >
                          {item.crm_match.account_name}
                        </Link>{' '}
                        · status {item.crm_match.deal_status} · via {item.crm_match.match_type}
                      </p>
                      {item.proposed_crm_update?.interpretation && (
                        <p className="mt-1 text-xs text-indigo-700">
                          {item.proposed_crm_update.interpretation}
                        </p>
                      )}
                      <p className="mt-1 font-mono text-[10px] text-neutral-400">
                        {item.gmail_message_id}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="shrink-0 rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white hover:bg-navy-700"
                      onClick={() => loadPreview.mutate(item.gmail_message_id)}
                    >
                      Review CRM update
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {preview && previewId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/40 p-4">
          <div className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-lg bg-white p-5 shadow-xl">
            <h3 className="text-lg font-semibold text-neutral-900">Approve CRM update from email</h3>
            <p className="mt-1 text-sm text-neutral-600">{preview.summary}</p>
            <p className="mt-3 text-sm font-medium">{preview.account_name}</p>
            <p className="text-xs text-neutral-500">
              Match · {preview.match_type} · {preview.email.direction}
            </p>
            <p className="mt-2 text-sm text-neutral-700">{preview.email.subject}</p>
            <p className="text-sm text-neutral-600">{preview.email.snippet}</p>
            {preview.interpretation && (
              <p className="mt-3 rounded-md bg-indigo-50 px-3 py-2 text-sm text-indigo-900">
                {preview.interpretation}
              </p>
            )}
            {preview.status_note && (
              <p className="mt-2 text-xs text-neutral-500">{preview.status_note}</p>
            )}
            <p className="mt-3 text-sm font-medium">Current</p>
            <ul className="mt-1 list-inside list-disc text-sm text-neutral-600">
              {Object.entries(preview.current || {}).map(([k, v]) => (
                <li key={k}>
                  {k}: {String(v ?? '—')}
                </li>
              ))}
            </ul>
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
                onClick={() => {
                  setPreview(null)
                  setPreviewId(null)
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white"
                onClick={() => approve.mutate(previewId)}
              >
                {approve.isPending ? 'Saving…' : 'Approve into CRM'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
