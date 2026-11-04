import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FilePen, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { apiRequest } from '../../api/client'
import { AccountSwitcher } from '../../components/AccountSwitcher'
import { FictionalBadge } from '../../components/FictionalBadge'
import { getWorkspaceAccountId } from '../../lib/workspaceAccount'

type Completeness = { complete: boolean; missing: string[] }

type ProposalDraft = {
  title?: string
  executive_summary?: string
  customer_requirements?: string[]
  proposed_solution?: string
  engagement_outline?: string[]
  commercial_note?: string
  open_questions?: string[]
  assumptions?: string[]
  next_steps?: string[]
  sources_used?: Array<{ type: string; ref: string }>
  status_note?: string
}

type DraftsPayload = {
  account_id: string
  account_name: string
  opportunity_name: string | null
  deal_status: string
  contact_name: string | null
  product_interest: string | null
  as_of_date: string
  followup: {
    subject: string | null
    body: string | null
    status: string
    next_followup_recommendation: string | null
  }
  proposal: {
    generated: boolean
    title: string | null
    draft: ProposalDraft | null
    status: string
  }
  completeness: Completeness
  notice: string
}

type Tab = 'followup' | 'proposal'

function StatusPill({ status }: { status: string }) {
  const styles =
    status === 'approved'
      ? 'border-green-600/40 bg-green-50 text-green-700'
      : status === 'rejected'
        ? 'border-neutral-300 bg-neutral-50 text-neutral-600'
        : status === 'draft'
          ? 'border-indigo-300 bg-indigo-50 text-indigo-800'
          : 'border-neutral-200 bg-white text-neutral-500'
  return (
    <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium capitalize ${styles}`}>
      {status || 'none'}
    </span>
  )
}

export function DraftsPage() {
  const { accountId: routeId } = useParams()
  const accountId = routeId || getWorkspaceAccountId() || ''
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('followup')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [execSummary, setExecSummary] = useState('')
  const [proposedSolution, setProposedSolution] = useState('')
  const [toast, setToast] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['drafts', accountId],
    queryFn: () => apiRequest<DraftsPayload>(`/api/v1/accounts/${accountId}/drafts`),
    enabled: !!accountId,
  })

  useEffect(() => {
    if (!data) return
    if (tab === 'followup') {
      setSubject(data.followup.subject || '')
      setBody(data.followup.body || '')
    } else {
      setSubject(data.proposal.title || data.proposal.draft?.title || '')
      setExecSummary(data.proposal.draft?.executive_summary || '')
      setProposedSolution(data.proposal.draft?.proposed_solution || '')
    }
  }, [data, tab])

  const invalidate = () => void qc.invalidateQueries({ queryKey: ['drafts', accountId] })

  const generateFollowup = useMutation({
    mutationFn: () =>
      apiRequest<DraftsPayload>(`/api/v1/accounts/${accountId}/drafts/followup`, {
        method: 'POST',
      }),
    onSuccess: (d) => {
      void qc.setQueryData(['drafts', accountId], d)
      setToast('Follow-up draft generated. Nothing was sent.')
      setTab('followup')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Generate failed'),
  })

  const generateProposal = useMutation({
    mutationFn: () =>
      apiRequest<DraftsPayload>(`/api/v1/accounts/${accountId}/drafts/proposal`, {
        method: 'POST',
      }),
    onSuccess: (d) => {
      void qc.setQueryData(['drafts', accountId], d)
      setToast('Proposal outline generated. Nothing was sent.')
      setTab('proposal')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Generate failed'),
  })

  const draftType = tab === 'followup' ? 'followup_email' : 'proposal_outline'
  const status = tab === 'followup' ? data?.followup.status : data?.proposal.status
  const editable = status === 'draft'

  const save = useMutation({
    mutationFn: () =>
      apiRequest<DraftsPayload>(`/api/v1/accounts/${accountId}/drafts/${draftType}`, {
        method: 'PATCH',
        body: JSON.stringify(
          tab === 'followup'
            ? { subject, body }
            : {
                subject,
                sections: {
                  executive_summary: execSummary,
                  proposed_solution: proposedSolution,
                },
              },
        ),
      }),
    onSuccess: (d) => {
      void qc.setQueryData(['drafts', accountId], d)
      setToast('Draft saved.')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Save failed'),
  })

  const approve = useMutation({
    mutationFn: () =>
      apiRequest<DraftsPayload>(
        `/api/v1/accounts/${accountId}/drafts/${draftType}/approve`,
        { method: 'POST' },
      ),
    onMutate: () => setToast('Approved — nothing was sent. Deal status unchanged.'),
    onSuccess: (d) => {
      void qc.setQueryData(['drafts', accountId], d)
      setToast(d.notice || 'Approved — nothing was sent.')
    },
    onError: (e) => {
      invalidate()
      setToast(e instanceof Error ? e.message : 'Approve failed')
    },
  })

  const reject = useMutation({
    mutationFn: () =>
      apiRequest<DraftsPayload>(
        `/api/v1/accounts/${accountId}/drafts/${draftType}/reject`,
        { method: 'POST' },
      ),
    onSuccess: (d) => {
      void qc.setQueryData(['drafts', accountId], d)
      setToast(d.notice || 'Rejected. Draft not ready to share.')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Reject failed'),
  })

  const generating = generateFollowup.isPending || generateProposal.isPending
  const proposal = data?.proposal.draft

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap gap-3 text-sm">
            <Link to={`/accounts/${accountId}/meetings`} className="text-navy-600 hover:underline">
              Meetings →
            </Link>
            <Link to={`/accounts/${accountId}/blockers`} className="text-navy-600 hover:underline">
              Blockers →
            </Link>
            <Link to={`/accounts/${accountId}/handoff`} className="text-navy-600 hover:underline">
              Handoff →
            </Link>
          </div>
          <h2 className="mt-2 flex items-center gap-2 text-2xl font-semibold text-neutral-900">
            <FilePen className="size-6 text-navy-600" />
            Follow-up & proposal drafts
          </h2>
          <p className="mt-1 text-sm text-neutral-500">
            Pick a CRM account · drafts you still own (nothing sent)
          </p>
        </div>
        <FictionalBadge />
      </div>

      <AccountSwitcher accountId={routeId} feature="drafts" />

      {toast && (
        <div className="rounded-md border border-green-600/30 bg-green-50 px-4 py-2 text-sm text-green-700">
          {toast}
        </div>
      )}

      {isLoading && <p className="text-neutral-500">Loading drafts…</p>}
      {error && (
        <p className="text-red-600">{error instanceof Error ? error.message : 'Failed to load'}</p>
      )}

      {data && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setTab('followup')}
                className={[
                  'cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium',
                  tab === 'followup'
                    ? 'border-navy-600 bg-navy-600 text-white'
                    : 'border-neutral-300 bg-white text-neutral-700 hover:bg-navy-50',
                ].join(' ')}
              >
                Follow-up email
              </button>
              <button
                type="button"
                onClick={() => setTab('proposal')}
                className={[
                  'cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium',
                  tab === 'proposal'
                    ? 'border-navy-600 bg-navy-600 text-white'
                    : 'border-neutral-300 bg-white text-neutral-700 hover:bg-navy-50',
                ].join(' ')}
              >
                Proposal outline
              </button>
              <StatusPill status={status || 'none'} />
            </div>

            <p className="rounded-md border border-indigo-200 bg-indigo-50/60 px-3 py-2 text-xs text-indigo-900">
              {data.notice}
            </p>

            {tab === 'followup' ? (
              <section className="space-y-3 rounded-lg border border-neutral-200 bg-white p-4">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={generating}
                    onClick={() => generateFollowup.mutate()}
                    className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                  >
                    <Sparkles className="size-4" />
                    {generateFollowup.isPending ? 'Generating…' : 'Generate follow-up'}
                  </button>
                </div>
                {!data.followup.body && status === 'none' ? (
                  <p className="text-sm text-neutral-500">Generate a draft to get started.</p>
                ) : (
                  <>
                    <label className="block text-xs font-medium text-neutral-500 uppercase">
                      Subject
                      <input
                        value={subject}
                        disabled={!editable}
                        onChange={(e) => setSubject(e.target.value)}
                        className="mt-1 w-full rounded-md border border-neutral-300 p-2 text-sm text-neutral-900 disabled:bg-neutral-50"
                      />
                    </label>
                    <label className="block text-xs font-medium text-neutral-500 uppercase">
                      Body
                      <textarea
                        value={body}
                        disabled={!editable}
                        onChange={(e) => setBody(e.target.value)}
                        rows={14}
                        className="mt-1 w-full rounded-md border border-neutral-300 p-3 text-sm leading-relaxed text-neutral-900 disabled:bg-neutral-50"
                      />
                    </label>
                  </>
                )}
              </section>
            ) : (
              <section className="space-y-3 rounded-lg border border-neutral-200 bg-white p-4">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={generating}
                    onClick={() => generateProposal.mutate()}
                    className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                  >
                    <Sparkles className="size-4" />
                    {generateProposal.isPending ? 'Generating…' : 'Generate proposal'}
                  </button>
                </div>
                {!proposal && status === 'none' ? (
                  <p className="text-sm text-neutral-500">Generate a draft to get started.</p>
                ) : (
                  <>
                    <label className="block text-xs font-medium text-neutral-500 uppercase">
                      Title
                      <input
                        value={subject}
                        disabled={!editable}
                        onChange={(e) => setSubject(e.target.value)}
                        className="mt-1 w-full rounded-md border border-neutral-300 p-2 text-sm disabled:bg-neutral-50"
                      />
                    </label>
                    <label className="block text-xs font-medium text-neutral-500 uppercase">
                      Executive summary
                      <textarea
                        value={execSummary}
                        disabled={!editable}
                        onChange={(e) => setExecSummary(e.target.value)}
                        rows={4}
                        className="mt-1 w-full rounded-md border border-neutral-300 p-3 text-sm disabled:bg-neutral-50"
                      />
                    </label>
                    <label className="block text-xs font-medium text-neutral-500 uppercase">
                      Proposed solution
                      <textarea
                        value={proposedSolution}
                        disabled={!editable}
                        onChange={(e) => setProposedSolution(e.target.value)}
                        rows={5}
                        className="mt-1 w-full rounded-md border border-neutral-300 p-3 text-sm disabled:bg-neutral-50"
                      />
                    </label>
                    {proposal?.customer_requirements && (
                      <div>
                        <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                          Requirements used
                        </p>
                        <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-neutral-700">
                          {proposal.customer_requirements.map((r) => (
                            <li key={r}>{r}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {proposal?.open_questions && proposal.open_questions.length > 0 && (
                      <div className="rounded-md border border-amber-600/20 bg-amber-50 px-3 py-2">
                        <p className="text-xs font-medium text-amber-900 uppercase">Open questions</p>
                        <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-amber-900">
                          {proposal.open_questions.map((q) => (
                            <li key={q}>{q}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <p className="text-sm text-neutral-600">
                      <span className="font-medium">Commercial note:</span>{' '}
                      {proposal?.commercial_note ||
                        'Pricing requires an approved quote — not stated here.'}
                    </p>
                  </>
                )}
              </section>
            )}

            {(status === 'draft' || status === 'approved' || status === 'rejected') && (
              <div className="flex flex-wrap items-center gap-2 border-t border-neutral-100 pt-3">
                {editable && (
                  <button
                    type="button"
                    disabled={save.isPending}
                    onClick={() => save.mutate()}
                    className="cursor-pointer rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                  >
                    Save edits
                  </button>
                )}
                {editable && (
                  <>
                    <button
                      type="button"
                      disabled={approve.isPending}
                      onClick={() => approve.mutate()}
                      className="cursor-pointer rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      disabled={reject.isPending}
                      onClick={() => reject.mutate()}
                      className="cursor-pointer rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-700"
                    >
                      Reject
                    </button>
                  </>
                )}
                <p className="text-xs text-neutral-500">
                  Approve = ready for you to use. Neither sends email nor marks the deal won.
                </p>
              </div>
            )}
          </div>

          <aside className="space-y-4">
            <section className="rounded-lg border border-amber-600/20 bg-amber-50 p-4">
              <p className="text-xs font-medium tracking-wide text-amber-900 uppercase">
                Completeness
              </p>
              <p className="mt-1 text-sm font-medium text-amber-950">
                {data.completeness.complete ? 'Ready enough to draft' : 'Gaps to watch'}
              </p>
              {data.completeness.missing.length === 0 ? (
                <p className="mt-2 text-sm text-amber-900">No completeness flags on this account.</p>
              ) : (
                <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-amber-950">
                  {data.completeness.missing.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              )}
            </section>

            <section className="rounded-lg border border-neutral-200 bg-white p-4">
              <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">Account</p>
              <p className="mt-2 text-sm font-medium text-neutral-900">{data.account_name}</p>
              <p className="text-xs text-neutral-500">{data.account_id}</p>
              <dl className="mt-3 space-y-1 text-sm text-neutral-700">
                <div>
                  <dt className="text-xs text-neutral-400">Contact</dt>
                  <dd>{data.contact_name || '—'}</dd>
                </div>
                <div>
                  <dt className="text-xs text-neutral-400">Interest</dt>
                  <dd>{data.product_interest || '—'}</dd>
                </div>
                <div>
                  <dt className="text-xs text-neutral-400">Deal status</dt>
                  <dd className="capitalize">{data.deal_status}</dd>
                </div>
              </dl>
            </section>

            {proposal?.sources_used && proposal.sources_used.length > 0 && tab === 'proposal' && (
              <section className="rounded-lg border border-neutral-200 bg-white p-4">
                <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                  Sources used
                </p>
                <ul className="mt-2 space-y-1 text-xs text-neutral-600">
                  {proposal.sources_used.map((s) => (
                    <li key={`${s.type}-${s.ref}`}>
                      <span className="font-medium text-navy-700">{s.type}</span> · {s.ref}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </aside>
        </div>
      )}
    </div>
  )
}
