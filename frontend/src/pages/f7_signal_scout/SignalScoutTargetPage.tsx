import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Radar, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { apiRequest } from '../../api/client'
import { FictionalBadge } from '../../components/FictionalBadge'

type Target = {
  target_id: string
  account_id: string | null
  name: string
  website_url: string
  source: string
  last_scanned_at: string | null
  scan_in_progress: boolean
  deal_status?: string
  recovery_link?: string | null
  signal_on_file?: {
    detected: boolean
    title: string | null
    classification: string | null
    source_url: string | null
  }
  notice: string
  data_label: string
}

type Scan = {
  scan_id: string
  status: string
  mode: string
  progress_pct: number
  stage: string | null
  label: string | null
  signal_count: number
  opportunity_count: number
  page_outcomes: Array<{ url?: string; status?: string; title?: string }>
  error_summary: string | null
}

type Signal = {
  signal_id: string
  signal_type: string
  title: string
  summary: string | null
  evidence: Array<{ url: string; published_date?: string; snippet: string }>
}

type Opportunity = {
  opportunity_id: string
  title: string
  summary: string | null
  score: number
  factors: Array<{ key: string; label: string; points: number }>
  signal_types: string[]
  status: string
  explanation?: {
    facts?: Array<{ layer: string; text: string }>
    interpretation?: { text: string }
    recommended_action?: { text: string }
    source?: string
  } | null
}

export function SignalScoutTargetPage() {
  const { targetId = '' } = useParams()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'signals' | 'opportunities'>('signals')
  const [scanId, setScanId] = useState<string | null>(null)
  const [selectedOpp, setSelectedOpp] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const { data: target, isLoading, error } = useQuery({
    queryKey: ['signal-scout-target', targetId],
    queryFn: () => apiRequest<Target>(`/api/v1/signal-scout/targets/${targetId}`),
    enabled: !!targetId,
  })

  const { data: scan } = useQuery({
    queryKey: ['signal-scout-scan', scanId],
    queryFn: () => apiRequest<Scan>(`/api/v1/signal-scout/scans/${scanId}`),
    enabled: !!scanId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s === 'queued' || s === 'running' ? 800 : false
    },
  })

  const signals = useQuery({
    queryKey: ['signal-scout-signals', targetId],
    queryFn: () =>
      apiRequest<{ items: Signal[] }>(`/api/v1/signal-scout/targets/${targetId}/signals`),
    enabled: !!targetId,
  })

  const opportunities = useQuery({
    queryKey: ['signal-scout-opps', targetId],
    queryFn: () =>
      apiRequest<{ items: Opportunity[]; notice: string }>(
        `/api/v1/signal-scout/targets/${targetId}/opportunities`,
      ),
    enabled: !!targetId,
  })

  const oppDetail = useQuery({
    queryKey: ['signal-scout-opp', selectedOpp],
    queryFn: () =>
      apiRequest<Opportunity & { signals: Signal[] }>(
        `/api/v1/signal-scout/opportunities/${selectedOpp}`,
      ),
    enabled: !!selectedOpp,
  })

  useEffect(() => {
    if (scan?.status === 'completed' || scan?.status === 'failed') {
      void qc.invalidateQueries({ queryKey: ['signal-scout-signals', targetId] })
      void qc.invalidateQueries({ queryKey: ['signal-scout-opps', targetId] })
      void qc.invalidateQueries({ queryKey: ['signal-scout-target', targetId] })
      if (scan.status === 'completed') {
        setToast(
          `Scan completed (${scan.mode}). ${scan.signal_count} signals, ${scan.opportunity_count} potential opportunities.`,
        )
        setTab(scan.opportunity_count > 0 ? 'opportunities' : 'signals')
      }
    }
  }, [scan?.status, scan?.mode, scan?.signal_count, scan?.opportunity_count, qc, targetId])

  const startScan = useMutation({
    mutationFn: () =>
      apiRequest<{ scan_id: string; status: string }>(
        `/api/v1/signal-scout/targets/${targetId}/scan`,
        { method: 'POST' },
      ),
    onSuccess: (d) => {
      setScanId(d.scan_id)
      setToast('Scan started…')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Scan failed to start'),
  })

  const explain = useMutation({
    mutationFn: (opportunityId: string) =>
      apiRequest<Opportunity>(`/api/v1/signal-scout/opportunities/${opportunityId}/explain`, {
        method: 'POST',
      }),
    onSuccess: (d) => {
      void qc.setQueryData(['signal-scout-opp', d.opportunity_id], d)
      setToast('Explanation ready (score unchanged).')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Explain failed'),
  })

  const scanning = scan?.status === 'queued' || scan?.status === 'running' || startScan.isPending

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/signal-scout" className="text-sm text-navy-600 hover:underline">
            ← Signal Scout
          </Link>
          <h2 className="mt-2 flex items-center gap-2 text-2xl font-semibold text-neutral-900">
            <Radar className="size-6 text-amber-700" />
            {target?.name || targetId}
          </h2>
          <p className="mt-1 text-sm text-neutral-500">
            {target?.account_id || 'Manual target'} ·{' '}
            {target?.website_url && (
              <a
                href={target.website_url}
                target="_blank"
                rel="noreferrer"
                className="text-navy-600 hover:underline"
              >
                {target.website_url}
              </a>
            )}
          </p>
        </div>
        <FictionalBadge />
      </div>

      {toast && (
        <div className="rounded-md border border-green-600/30 bg-green-50 px-4 py-2 text-sm text-green-700">
          {toast}
        </div>
      )}

      {isLoading && <p className="text-neutral-500">Loading target…</p>}
      {error && (
        <p className="text-red-600">{error instanceof Error ? error.message : 'Failed to load'}</p>
      )}

      {target && (
        <>
          <section className="rounded-lg border border-neutral-200 bg-white p-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-md bg-neutral-100 px-2 py-0.5 text-xs capitalize text-neutral-700">
                {target.source}
              </span>
              {target.signal_on_file?.detected && (
                <span className="rounded-md border border-green-600/30 bg-green-50 px-2 py-0.5 text-xs text-green-700">
                  Public signal on file
                </span>
              )}
              <span className="text-xs text-neutral-500">
                Last scanned: {target.last_scanned_at?.slice(0, 19) || 'Never'}
              </span>
            </div>
            {target.signal_on_file?.title && (
              <p className="text-sm text-neutral-700">
                On file: {target.signal_on_file.title}
                {target.signal_on_file.classification
                  ? ` (${target.signal_on_file.classification})`
                  : ''}
              </p>
            )}
            <p className="text-xs text-indigo-900">{target.notice}</p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={scanning}
                onClick={() => startScan.mutate()}
                className="cursor-pointer rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {scanning ? 'Scanning…' : 'Scan now'}
              </button>
              {target.recovery_link && (
                <Link
                  to={target.recovery_link}
                  className="rounded-md border border-amber-600/40 bg-amber-50 px-3 py-2 text-sm text-amber-950"
                >
                  Review in Lead Recovery
                </Link>
              )}
            </div>
            {scan && (
              <div className="rounded-md border border-neutral-100 bg-neutral-50 px-3 py-2 text-sm">
                <p className="font-medium text-neutral-800">
                  Scan {scan.status}
                  {scan.label ? ` · ${scan.label}` : ''}
                </p>
                <div className="mt-2 h-2 overflow-hidden rounded bg-neutral-200">
                  <div
                    className={[
                      'h-full rounded',
                      scan.status === 'failed' ? 'bg-red-500' : 'bg-green-600',
                    ].join(' ')}
                    style={{ width: `${scan.progress_pct || 0}%` }}
                  />
                </div>
                {scan.error_summary && (
                  <p className="mt-2 text-xs text-red-600">{scan.error_summary}</p>
                )}
              </div>
            )}
          </section>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setTab('signals')}
              className={[
                'cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium',
                tab === 'signals'
                  ? 'border-navy-600 bg-navy-600 text-white'
                  : 'border-neutral-300 bg-white text-neutral-700',
              ].join(' ')}
            >
              Signals ({signals.data?.items.length ?? 0})
            </button>
            <button
              type="button"
              onClick={() => setTab('opportunities')}
              className={[
                'cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium',
                tab === 'opportunities'
                  ? 'border-amber-700 bg-amber-700 text-white'
                  : 'border-neutral-300 bg-white text-neutral-700',
              ].join(' ')}
            >
              Potential opportunities ({opportunities.data?.items.length ?? 0})
            </button>
          </div>

          {tab === 'signals' && (
            <div className="space-y-3">
              {(signals.data?.items || []).length === 0 ? (
                <p className="rounded-lg border border-neutral-200 bg-white px-4 py-6 text-sm text-neutral-600">
                  No validated signals yet. Run Scan now — failed pages will not invent evidence.
                </p>
              ) : (
                signals.data!.items.map((s) => (
                  <section
                    key={s.signal_id}
                    className="rounded-lg border border-neutral-200 bg-white p-4 space-y-2"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded bg-navy-50 px-2 py-0.5 text-xs text-navy-800">
                        {s.signal_type}
                      </span>
                      <h3 className="text-sm font-semibold text-neutral-900">{s.title}</h3>
                    </div>
                    {s.summary && <p className="text-sm text-neutral-700">{s.summary}</p>}
                    <ul className="space-y-2">
                      {s.evidence.map((e) => (
                        <li
                          key={`${e.url}-${e.snippet.slice(0, 24)}`}
                          className="rounded border border-neutral-100 p-3 text-sm"
                        >
                          <p className="text-neutral-800">“{e.snippet}”</p>
                          <p className="mt-1 text-xs text-neutral-400">
                            {e.published_date || 'unavailable'}
                          </p>
                          <a
                            href={e.url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-1 inline-block text-xs text-navy-600 hover:underline"
                          >
                            Open source page
                          </a>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))
              )}
            </div>
          )}

          {tab === 'opportunities' && (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
              <div className="space-y-3">
                <p className="text-xs text-amber-900">
                  {opportunities.data?.notice ||
                    'Potential ≠ committed pipeline. Score is rules-only.'}
                </p>
                {(opportunities.data?.items || []).length === 0 ? (
                  <p className="rounded-lg border border-neutral-200 bg-white px-4 py-6 text-sm text-neutral-600">
                    No potential opportunity yet (need ≥2 validated related signals).
                  </p>
                ) : (
                  opportunities.data!.items.map((o) => (
                    <button
                      key={o.opportunity_id}
                      type="button"
                      onClick={() => setSelectedOpp(o.opportunity_id)}
                      className={[
                        'w-full cursor-pointer rounded-lg border p-4 text-left',
                        selectedOpp === o.opportunity_id
                          ? 'border-amber-600 bg-amber-50'
                          : 'border-neutral-200 bg-white hover:bg-amber-50/40',
                      ].join(' ')}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="text-sm font-semibold text-neutral-900">{o.title}</h3>
                        <span className="rounded-md border border-amber-600/40 bg-amber-50 px-2 py-0.5 text-sm font-semibold text-amber-900">
                          {o.score}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-neutral-500">{o.signal_types?.join(' · ')}</p>
                    </button>
                  ))
                )}
              </div>

              <aside className="space-y-3">
                {oppDetail.data ? (
                  <section className="rounded-lg border border-amber-600/20 bg-white p-4 space-y-3">
                    <p className="text-xs font-medium uppercase text-neutral-500">Opportunity detail</p>
                    <p className="text-2xl font-semibold text-amber-900">{oppDetail.data.score}/100</p>
                    <p className="text-sm text-neutral-700">{oppDetail.data.summary}</p>
                    <ul className="space-y-1 text-sm text-neutral-700">
                      {(oppDetail.data.factors || []).map((f) => (
                        <li key={f.key} className="flex justify-between gap-2">
                          <span>{f.label}</span>
                          <span className="font-medium">{f.points}</span>
                        </li>
                      ))}
                    </ul>
                    <button
                      type="button"
                      disabled={explain.isPending}
                      onClick={() => explain.mutate(oppDetail.data!.opportunity_id)}
                      className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                    >
                      <Sparkles className="size-4" />
                      {explain.isPending ? 'Explaining…' : 'Explain with AI'}
                    </button>
                    {oppDetail.data.explanation && (
                      <div className="rounded-md border border-indigo-200 bg-indigo-50/60 p-3 text-sm text-indigo-950 space-y-2">
                        <p>{oppDetail.data.explanation.interpretation?.text}</p>
                        <p className="text-xs">
                          Next: {oppDetail.data.explanation.recommended_action?.text}
                        </p>
                        <p className="text-xs text-indigo-700">
                          Source: {oppDetail.data.explanation.source || 'rules'} (score unchanged)
                        </p>
                      </div>
                    )}
                  </section>
                ) : (
                  <p className="text-sm text-neutral-500">Select a potential opportunity.</p>
                )}
              </aside>
            </div>
          )}
        </>
      )}
    </div>
  )
}
