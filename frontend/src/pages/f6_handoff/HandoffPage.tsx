import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Handshake, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { apiRequest } from '../../api/client'
import { AccountSwitcher } from '../../components/AccountSwitcher'
import { FictionalBadge } from '../../components/FictionalBadge'
import { getWorkspaceAccountId } from '../../lib/workspaceAccount'

type HandoffPack = {
  stakeholders: Array<{ name: string; role: string; is_decision_maker?: boolean }>
  confirmed_requirements: string[]
  open_items: string[]
  timeline: string[]
  products: Array<{ name: string; reference_url?: string; claim_text?: string }>
  proposal_summary: string | null
  delivery_notes: string
  checklist: Array<{ task: string; owner: string; status: string; due_date?: string | null }>
}

type HandoffPayload = {
  account_id: string
  account_name: string
  opportunity_name: string | null
  deal_status: string
  deal_value: number
  currency: string
  handoff_required: boolean
  handoff_status: string
  handoff_created_date: string | null
  handoff_pack: HandoffPack | null
  can_mark_won: boolean
  notice: string
  as_of_date: string
}

function money(n: number, currency = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency || 'USD',
    maximumFractionDigits: 0,
  }).format(n)
}

function StatusPill({ status, dealStatus }: { status: string; dealStatus: string }) {
  if (dealStatus === 'won') {
    return (
      <span className="inline-flex rounded-md border border-green-600/40 bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
        Won
      </span>
    )
  }
  return (
    <span className="inline-flex rounded-md border border-neutral-300 bg-neutral-50 px-2 py-0.5 text-xs font-medium capitalize text-neutral-600">
      {dealStatus}
    </span>
  )
}

export function HandoffPage() {
  const { accountId: routeId } = useParams()
  const accountId = routeId || getWorkspaceAccountId() || ''
  const qc = useQueryClient()
  const [confirmWon, setConfirmWon] = useState(false)
  const [showMarkWon, setShowMarkWon] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['handoff', accountId],
    queryFn: () => apiRequest<HandoffPayload>(`/api/v1/accounts/${accountId}/handoff`),
    enabled: !!accountId,
  })

  const markWon = useMutation({
    mutationFn: () =>
      apiRequest<HandoffPayload>(`/api/v1/accounts/${accountId}/mark-won`, {
        method: 'POST',
        body: JSON.stringify({ confirm: true }),
      }),
    onSuccess: (d) => {
      void qc.setQueryData(['handoff', accountId], d)
      setShowMarkWon(false)
      setConfirmWon(false)
      setToast(d.notice || 'Deal marked won. Nothing was emailed.')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Mark won failed'),
  })

  const generate = useMutation({
    mutationFn: () =>
      apiRequest<HandoffPayload>(`/api/v1/accounts/${accountId}/handoff/generate`, {
        method: 'POST',
      }),
    onSuccess: (d) => {
      void qc.setQueryData(['handoff', accountId], d)
      setToast(d.notice || 'Handoff pack generated as draft.')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Generate failed'),
  })

  const approve = useMutation({
    mutationFn: () =>
      apiRequest<HandoffPayload>(`/api/v1/accounts/${accountId}/handoff/approve`, {
        method: 'POST',
      }),
    onSuccess: (d) => {
      void qc.setQueryData(['handoff', accountId], d)
      setToast(d.notice || 'Handoff approved. Nothing was emailed.')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Approve failed'),
  })

  const pack = data?.handoff_pack
  const isWon = data?.deal_status === 'won'
  const isApproved = data?.handoff_status === 'approved'
  const isDraft = data?.handoff_status === 'draft'

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap gap-3 text-sm">
            <Link to={`/accounts/${accountId}/drafts`} className="text-navy-600 hover:underline">
              Drafts →
            </Link>
            <Link to={`/accounts/${accountId}/blockers`} className="text-navy-600 hover:underline">
              Blockers →
            </Link>
          </div>
          <h2 className="mt-2 flex items-center gap-2 text-2xl font-semibold text-neutral-900">
            <Handshake className="size-6 text-navy-600" />
            Customer handoff
          </h2>
          <p className="mt-1 text-sm text-neutral-500">
            Pick a CRM account · pack context for delivery — no tickets sent
          </p>
        </div>
        <FictionalBadge />
      </div>

      <AccountSwitcher
        accountId={routeId}
        feature="handoff"
        demoAccountIds={['ACC-0015', 'ACC-0181']}
      />

      {toast && (
        <div className="rounded-md border border-green-600/30 bg-green-50 px-4 py-2 text-sm text-green-700">
          {toast}
        </div>
      )}

      {isLoading && <p className="text-neutral-500">Loading handoff…</p>}
      {error && (
        <p className="text-red-600">{error instanceof Error ? error.message : 'Failed to load'}</p>
      )}

      {data && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={data.handoff_status} dealStatus={data.deal_status} />
            {isWon && (
              <span
                className={[
                  'inline-flex rounded-md border px-2 py-0.5 text-xs font-medium capitalize',
                  isApproved
                    ? 'border-green-600/40 bg-green-50 text-green-700'
                    : 'border-indigo-300 bg-indigo-50 text-indigo-800',
                ].join(' ')}
              >
                Handoff: {data.handoff_status}
              </span>
            )}
            <span className="text-sm text-neutral-600">
              {money(data.deal_value, data.currency)}
              {data.opportunity_name ? ` · ${data.opportunity_name}` : ''}
            </span>
          </div>

          <p className="rounded-md border border-indigo-200 bg-indigo-50/60 px-3 py-2 text-xs text-indigo-900">
            {data.notice}
          </p>

          {!isWon && (
            <section className="rounded-lg border border-amber-600/30 bg-amber-50 p-4 space-y-3">
              <p className="text-sm font-semibold text-amber-950">
                Deal not won — mark won to enable handoff
              </p>
              <p className="text-sm text-amber-900">
                Approving a proposal does not mark the deal won. Handoff starts only after an
                explicit confirm.
              </p>
              {!showMarkWon ? (
                <button
                  type="button"
                  disabled={!data.can_mark_won}
                  onClick={() => setShowMarkWon(true)}
                  className="cursor-pointer rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Mark won…
                </button>
              ) : (
                <div className="space-y-3 rounded-md border border-navy-200 bg-white p-3">
                  <label className="flex cursor-pointer items-start gap-2 text-sm text-neutral-800">
                    <input
                      type="checkbox"
                      checked={confirmWon}
                      onChange={(e) => setConfirmWon(e.target.checked)}
                      className="mt-1"
                    />
                    <span>
                      I confirm this deal is won. This does not send email or create delivery
                      tickets.
                    </span>
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={!confirmWon || markWon.isPending}
                      onClick={() => markWon.mutate()}
                      className="cursor-pointer rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {markWon.isPending ? 'Updating…' : 'Confirm mark won'}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setShowMarkWon(false)
                        setConfirmWon(false)
                      }}
                      className="cursor-pointer rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-700"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
              {!data.can_mark_won && (
                <p className="text-xs text-amber-800">
                  Mark won is available for open deals only. Try ACC-0181 after the F5 path, or open
                  a pre-seeded won account such as ACC-0015.
                </p>
              )}
            </section>
          )}

          {isWon && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={generate.isPending}
                onClick={() => generate.mutate()}
                className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                <Sparkles className="size-4" />
                {generate.isPending
                  ? 'Generating…'
                  : pack
                    ? 'Regenerate handoff pack'
                    : 'Generate handoff pack'}
              </button>
              {pack && isDraft && (
                <button
                  type="button"
                  disabled={approve.isPending}
                  onClick={() => approve.mutate()}
                  className="cursor-pointer rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                >
                  Approve handoff
                </button>
              )}
            </div>
          )}

          {isWon && !pack && (
            <p className="rounded-lg border border-neutral-200 bg-white px-4 py-6 text-sm text-neutral-600">
              No handoff pack yet. Generate one from CRM requirements, stakeholders, and approved
              proposal context.
            </p>
          )}

          {pack && (
            <div className="grid gap-4 lg:grid-cols-2">
              <section className="rounded-lg border border-neutral-200 bg-white p-4 space-y-2">
                <h3 className="text-sm font-semibold text-neutral-900">Stakeholders</h3>
                <ul className="space-y-2 text-sm text-neutral-700">
                  {pack.stakeholders.map((s) => (
                    <li key={`${s.name}-${s.role}`} className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{s.name}</span>
                      <span className="text-neutral-500">{s.role}</span>
                      {s.is_decision_maker && (
                        <span className="rounded bg-green-50 px-1.5 py-0.5 text-xs text-green-700">
                          decision maker
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </section>

              <section className="rounded-lg border border-neutral-200 bg-white p-4 space-y-2">
                <h3 className="text-sm font-semibold text-neutral-900">Confirmed requirements</h3>
                <ul className="list-disc space-y-1 pl-5 text-sm text-neutral-700">
                  {pack.confirmed_requirements.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </section>

              <section className="rounded-lg border border-amber-600/20 bg-amber-50 p-4 space-y-2 lg:col-span-2">
                <h3 className="text-sm font-semibold text-amber-950">Open items / delivery risks</h3>
                {pack.open_items.length === 0 ? (
                  <p className="text-sm text-amber-900">No open delivery risks on file.</p>
                ) : (
                  <ul className="list-disc space-y-1 pl-5 text-sm text-amber-950">
                    {pack.open_items.map((i) => (
                      <li key={i}>{i}</li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="rounded-lg border border-neutral-200 bg-white p-4 space-y-2">
                <h3 className="text-sm font-semibold text-neutral-900">Timeline</h3>
                <ul className="list-disc space-y-1 pl-5 text-sm text-neutral-700">
                  {pack.timeline.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              </section>

              <section className="rounded-lg border border-neutral-200 bg-white p-4 space-y-2">
                <h3 className="text-sm font-semibold text-neutral-900">Products</h3>
                <ul className="space-y-2 text-sm text-neutral-700">
                  {pack.products.map((p) => (
                    <li key={p.name}>
                      <p className="font-medium text-navy-700">{p.name}</p>
                      {p.claim_text && <p className="text-xs text-neutral-500">“{p.claim_text}”</p>}
                      {p.reference_url && (
                        <a
                          href={p.reference_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-navy-600 hover:underline"
                        >
                          Source
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              </section>

              {pack.proposal_summary && (
                <section className="rounded-lg border border-neutral-200 bg-white p-4 space-y-2 lg:col-span-2">
                  <h3 className="text-sm font-semibold text-neutral-900">
                    Approved proposal summary
                  </h3>
                  <p className="text-sm text-neutral-700">{pack.proposal_summary}</p>
                </section>
              )}

              <section className="rounded-lg border border-neutral-200 bg-white p-4 space-y-2 lg:col-span-2">
                <h3 className="text-sm font-semibold text-neutral-900">Delivery notes</h3>
                <p className="text-sm leading-relaxed text-neutral-700">{pack.delivery_notes}</p>
              </section>

              {pack.checklist.length > 0 && (
                <section className="rounded-lg border border-neutral-200 bg-white p-4 space-y-2 lg:col-span-2">
                  <h3 className="text-sm font-semibold text-neutral-900">Onboarding checklist</h3>
                  <ul className="divide-y divide-neutral-100 text-sm">
                    {pack.checklist.map((c) => (
                      <li key={c.task} className="flex flex-wrap justify-between gap-2 py-2">
                        <span className="text-neutral-800">{c.task}</span>
                        <span className="text-xs text-neutral-500">
                          {c.owner} · {c.status}
                          {c.due_date ? ` · ${c.due_date}` : ''}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
