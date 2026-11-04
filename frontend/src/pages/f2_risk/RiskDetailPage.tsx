import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { apiRequest } from '../../api/client'
import { FictionalBadge } from '../../components/FictionalBadge'

type Factor = {
  key: string
  label: string
  points: number
  max_points: number
  detail: string
}

type RiskDetail = {
  account_id: string
  account_name: string
  opportunity_name: string | null
  deal_status: string
  opportunity_stage: string | null
  deal_value: number
  currency: string
  contact_name: string | null
  is_decision_maker: boolean
  account_owner: string | null
  revenue_risk_score: number
  risk_category: string
  risk_reason: string | null
  recommended_next_action: string | null
  inactivity_days: number | null
  last_activity_date: string | null
  expected_close_date: string | null
  next_followup_date: string | null
  next_action: string | null
  next_action_date: string | null
  overdue_followup: boolean
  blocker: {
    detected: boolean
    category: string | null
    severity: string | null
    status: string | null
  }
  factors: Factor[]
  scoring_version: string
  explanation: {
    facts: Array<{ layer: string; text: string }>
    interpretation: { text: string }
    recommended_action: { text: string }
    source?: string
  }
  timeline: Array<{
    date?: string
    type?: string
    description?: string
    outcome?: string
  }>
  as_of_date: string
}

type ActionPreview = {
  summary: string
  recommended_next_action: string
  proposed_activity: { description: string; date: string; type: string }
  field_updates: Record<string, string | number>
  will_not_change: string[]
}

function money(n: number, currency = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency || 'USD',
    maximumFractionDigits: 0,
  }).format(n)
}

function BandPill({ band }: { band: string }) {
  const styles =
    band === 'high'
      ? 'bg-red-50 text-red-700 border-red-600/30'
      : band === 'medium'
        ? 'bg-amber-50 text-amber-700 border-amber-600/30'
        : 'bg-neutral-100 text-neutral-600 border-neutral-300'
  return (
    <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium capitalize ${styles}`}>
      {band}
    </span>
  )
}

export function RiskDetailPage() {
  const { accountId = '' } = useParams()
  const qc = useQueryClient()
  const [preview, setPreview] = useState<ActionPreview | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [explanation, setExplanation] = useState<RiskDetail['explanation'] | null>(null)
  const [aiNote, setAiNote] = useState<string | null>(null)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['risk', accountId],
    queryFn: () => apiRequest<RiskDetail>(`/api/v1/accounts/${accountId}/risk`),
    enabled: !!accountId,
  })

  // Warm Blockers cache so Risk → Resolve feels instant
  useEffect(() => {
    if (!data?.blocker.detected || !accountId) return
    void qc.prefetchQuery({
      queryKey: ['blocker', accountId],
      queryFn: () => apiRequest(`/api/v1/accounts/${accountId}/blocker`),
      staleTime: 60_000,
    })
  }, [data?.blocker.detected, accountId, qc])

  const explain = useMutation({
    mutationFn: () =>
      apiRequest<RiskDetail['explanation'] & { ai_unavailable?: boolean; source?: string }>(
        `/api/v1/accounts/${accountId}/risk/explain`,
        { method: 'POST' },
      ),
    onSuccess: (d) => {
      setExplanation(d)
      setAiNote(
        d.source === 'azure_openai'
          ? 'Explanation from Azure OpenAI (score unchanged).'
          : 'AI unavailable — showing rules / stored reason.',
      )
    },
  })

  const recompute = useMutation({
    mutationFn: () =>
      apiRequest(`/api/v1/accounts/${accountId}/risk/recompute`, { method: 'POST' }),
    onSuccess: () => {
      void refetch()
      void qc.invalidateQueries({ queryKey: ['risk'] })
      setToast('Score recomputed from rules only.')
    },
  })

  const loadPreview = useMutation({
    mutationFn: () =>
      apiRequest<ActionPreview>(`/api/v1/accounts/${accountId}/risk-action/preview`),
    onSuccess: setPreview,
  })

  const confirmAction = useMutation({
    mutationFn: () =>
      apiRequest(`/api/v1/accounts/${accountId}/risk-action/confirm`, {
        method: 'POST',
        body: JSON.stringify({ confirm: true }),
      }),
    onSuccess: () => {
      setPreview(null)
      void refetch()
      void qc.invalidateQueries({ queryKey: ['risk'] })
      setToast('Action logged. Deal status unchanged. Score recomputed.')
    },
  })

  if (isLoading) return <p className="text-neutral-500">Loading risk detail…</p>
  if (error || !data) {
    return (
      <p className="text-red-600">
        {error instanceof Error ? error.message : 'Failed to load risk detail'}
      </p>
    )
  }

  const expl = explanation ?? data.explanation

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/risk" className="text-sm text-navy-600 hover:underline">
            ← Risk list
          </Link>
          <h2 className="mt-2 text-2xl font-semibold text-neutral-900">{data.account_name}</h2>
          <p className="mt-1 text-sm text-neutral-500">
            {data.opportunity_name || data.account_id} · as of {data.as_of_date}
          </p>
        </div>
        <FictionalBadge />
      </div>

      {toast && (
        <div className="rounded-md border border-green-600/30 bg-green-50 px-4 py-2 text-sm text-green-700">
          {toast}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="rounded-lg border border-neutral-200 bg-white p-4 lg:col-span-2">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                Revenue risk score
              </p>
              <p className="mt-1 text-4xl font-semibold text-navy-700">{data.revenue_risk_score}</p>
              <p className="text-sm text-neutral-500">out of 100 · {data.scoring_version}</p>
            </div>
            <BandPill band={data.risk_category} />
          </div>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2 text-sm">
            <div>
              <dt className="text-neutral-500">Status / stage</dt>
              <dd className="font-medium capitalize text-neutral-800">
                {data.deal_status} · {data.opportunity_stage || '—'}
              </dd>
            </div>
            <div>
              <dt className="text-neutral-500">Value</dt>
              <dd className="font-medium text-neutral-800">{money(data.deal_value, data.currency)}</dd>
            </div>
            <div>
              <dt className="text-neutral-500">Inactivity</dt>
              <dd className="font-medium text-neutral-800">{data.inactivity_days ?? '—'} days</dd>
            </div>
            <div>
              <dt className="text-neutral-500">Expected close</dt>
              <dd className="font-medium text-neutral-800">{data.expected_close_date || '—'}</dd>
            </div>
            <div>
              <dt className="text-neutral-500">Contact</dt>
              <dd className="font-medium text-neutral-800">
                {data.contact_name || '—'}
                {data.is_decision_maker ? ' · decision maker' : ' · not decision maker'}
              </dd>
            </div>
            <div>
              <dt className="text-neutral-500">Follow-up</dt>
              <dd className={`font-medium ${data.overdue_followup ? 'text-amber-700' : 'text-neutral-800'}`}>
                {data.next_followup_date || data.next_action_date || '—'}
                {data.overdue_followup ? ' (overdue)' : ''}
              </dd>
            </div>
          </dl>
        </section>

        <section className="rounded-lg border border-neutral-200 bg-white p-4">
          <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">Recommended action</p>
          <p className="mt-2 text-sm text-neutral-800">
            {data.recommended_next_action || 'Review factor evidence with the account owner.'}
          </p>
          <div className="mt-4 flex flex-col gap-2">
            <button
              type="button"
              onClick={() => explain.mutate()}
              disabled={explain.isPending}
              className="inline-flex items-center justify-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              <Sparkles className="size-4" />
              {explain.isPending ? 'Explaining…' : 'Explain with AI'}
            </button>
            <button
              type="button"
              onClick={() => loadPreview.mutate()}
              disabled={loadPreview.isPending}
              className="rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white hover:bg-navy-700 disabled:opacity-60"
            >
              Log action to CRM
            </button>
            <button
              type="button"
              onClick={() => recompute.mutate()}
              disabled={recompute.isPending}
              className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-60"
            >
              Recompute score
            </button>
          </div>
        </section>
      </div>

      {data.blocker.detected && (
        <section className="rounded-lg border border-amber-600/30 bg-amber-50 px-4 py-3">
          <p className="text-sm font-semibold text-amber-900">Open blocker</p>
          <p className="mt-1 text-sm text-amber-800">
            {data.blocker.category} · {data.blocker.severity} · {data.blocker.status}
          </p>
          <p className="mt-2 text-sm text-amber-900">
            Risk shows that a blocker exists and how it affects the score. Answers with citations
            live in the Blocker workspace — not inside Risk.
          </p>
          <Link
            to={`/accounts/${data.account_id}/blockers?ask=1&category=${encodeURIComponent(data.blocker.category || '')}`}
            className="mt-2 inline-flex cursor-pointer text-sm font-medium text-navy-700 underline hover:text-navy-900"
          >
            Resolve this blocker →
          </Link>
        </section>
      )}

      <section className="rounded-lg border border-neutral-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-neutral-900">Factor breakdown</h3>
        <ul className="mt-4 space-y-3">
          {data.factors.map((f) => {
            const pct = f.max_points ? Math.round((f.points / f.max_points) * 100) : 0
            return (
              <li key={f.key}>
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-neutral-800">{f.label}</span>
                  <span className="text-neutral-500">
                    {f.points}/{f.max_points}
                  </span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded bg-neutral-100">
                  <div className="h-full rounded bg-navy-400" style={{ width: `${pct}%` }} />
                </div>
                <p className="mt-1 text-xs text-neutral-500">{f.detail}</p>
              </li>
            )
          })}
        </ul>
      </section>

      <section className="rounded-lg border border-neutral-200 bg-navy-800 p-4 text-neutral-0">
        <h3 className="text-sm font-semibold text-white">Explanation</h3>
        {aiNote && <p className="mt-1 text-xs text-indigo-300">{aiNote}</p>}
        <div className="mt-3 space-y-3 text-sm">
          {expl.facts.map((f, i) => (
            <div key={i}>
              <p className="text-xs font-medium tracking-wide text-navy-300 uppercase">Fact</p>
              <p className="mt-0.5 text-navy-100">{f.text}</p>
            </div>
          ))}
          <div>
            <p className="text-xs font-medium tracking-wide text-indigo-300 uppercase">Interpretation</p>
            <p className="mt-0.5 text-white">{expl.interpretation.text}</p>
          </div>
          <div>
            <p className="text-xs font-medium tracking-wide text-amber-300 uppercase">
              Recommended action
            </p>
            <p className="mt-0.5 text-white">{expl.recommended_action.text}</p>
          </div>
        </div>
        {data.risk_reason && (
          <p className="mt-3 border-t border-navy-700 pt-3 text-xs text-navy-300">
            Stored reason: {data.risk_reason}
          </p>
        )}
      </section>

      <section className="rounded-lg border border-neutral-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-neutral-900">Recent activity</h3>
        {data.timeline.length === 0 ? (
          <p className="mt-2 text-sm text-neutral-500">No activity history on this row.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {data.timeline.map((a, i) => (
              <li key={i} className="border-b border-neutral-100 pb-2 text-sm last:border-0">
                <p className="text-xs text-neutral-400">
                  {a.date || '—'} · {a.type || 'Activity'}
                </p>
                <p className="text-neutral-800">{a.description || a.outcome || '—'}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/50 p-4">
          <div className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-lg bg-white p-5 shadow-xl">
            <h3 className="text-lg font-semibold text-neutral-900">
              Review CRM updates before logging action
            </h3>
            <p className="mt-2 text-sm text-neutral-600">{preview.summary}</p>
            <p className="mt-3 text-sm text-neutral-800">
              <span className="font-medium">Recommended:</span> {preview.recommended_next_action}
            </p>
            <div className="mt-4 rounded-md bg-neutral-50 p-3 text-sm">
              <p className="font-medium text-neutral-700">Proposed activity</p>
              <p className="mt-1 text-neutral-600">{preview.proposed_activity.description}</p>
              <p className="mt-2 text-xs text-neutral-500">
                {preview.proposed_activity.date} · {preview.proposed_activity.type}
              </p>
            </div>
            <div className="mt-4">
              <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                Field updates
              </p>
              <ul className="mt-2 space-y-1 text-sm text-neutral-700">
                {Object.entries(preview.field_updates).map(([k, v]) => (
                  <li key={k}>
                    <span className="font-mono text-xs text-neutral-500">{k}</span> → {String(v)}
                  </li>
                ))}
              </ul>
            </div>
            <div className="mt-4">
              <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                Will not change
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-neutral-600">
                {preview.will_not_change.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setPreview(null)}
                className="rounded-md border border-neutral-300 px-3 py-2 text-sm text-neutral-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => confirmAction.mutate()}
                disabled={confirmAction.isPending}
                className="rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
              >
                {confirmAction.isPending ? 'Saving…' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
