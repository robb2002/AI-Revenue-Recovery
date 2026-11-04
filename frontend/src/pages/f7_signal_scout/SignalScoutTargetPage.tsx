import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExternalLink, Radar, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { ApiError, apiRequest } from '../../api/client'
import { FictionalBadge } from '../../components/FictionalBadge'
import {
  FactorBars,
  LiveScanPipeline,
  PipelineStrip,
  ScoreDonut,
  SignalTypeBars,
  SignalTypeDonut,
} from './ScoutCharts'

function hostFromUrl(url?: string | null) {
  if (!url) return null
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return null
  }
}

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
  pages?: Array<{
    page_id?: string
    url: string
    page_category: string
    status: string
    title?: string | null
  }>
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
  page_outcomes: Array<{
    url?: string
    status?: string
    title?: string
    page_category?: string
    page_type?: string
  }>
  error_summary: string | null
}

const HUB_ORDER = [
  'procurement',
  'technology',
  'digital_learning',
  'assessment',
  'funding',
  'leadership',
  'strategic_initiative',
  'partnership',
  'news',
] as const

function statusTone(status?: string) {
  const s = (status || '').toLowerCase()
  if (s === 'ok') return 'border-green-600/30 bg-green-50 text-green-800'
  if (s === 'skipped_robots') return 'border-amber-600/30 bg-amber-50 text-amber-900'
  if (s === 'domain_mismatch') return 'border-red-600/30 bg-red-50 text-red-800'
  return 'border-neutral-200 bg-neutral-50 text-neutral-700'
}

type Signal = {
  signal_id: string
  signal_type: string
  title: string
  summary: string | null
  evidence: Array<{ url: string; published_date?: string; snippet: string }>
}

type Factor = {
  key: string
  label: string
  points: number
  max_points?: number
  detail?: string
}

type Opportunity = {
  opportunity_id: string
  title: string
  summary: string | null
  score: number
  score_band?: string
  factors: Factor[]
  signal_types: string[]
  status: string
  explanation?: {
    facts?: Array<{ layer: string; text: string }>
    interpretation?: { text: string }
    recommended_action?: { text: string }
    source?: string
  } | null
}

function BandPill({ band }: { band?: string }) {
  const b = (band || '').toLowerCase()
  const styles =
    b === 'high'
      ? 'border-red-600/30 bg-red-50 text-red-700'
      : b === 'medium'
        ? 'border-amber-600/40 bg-amber-50 text-amber-800'
        : b === 'low'
          ? 'border-navy-300 bg-navy-50 text-navy-800'
          : 'border-neutral-300 bg-neutral-50 text-neutral-600'
  return (
    <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium capitalize ${styles}`}>
      {b || 'potential'}
    </span>
  )
}

function TypeChip({ type }: { type: string }) {
  return (
    <span className="rounded-md border border-navy-200 bg-navy-50 px-2 py-0.5 text-[11px] font-medium text-navy-800">
      {type.replaceAll('_', ' ')}
    </span>
  )
}

export function SignalScoutTargetPage() {
  const { targetId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const ensureAccount = searchParams.get('account')
  const qc = useQueryClient()
  const [tab, setTab] = useState<'signals' | 'opportunities'>('signals')
  const [scanId, setScanId] = useState<string | null>(null)
  const [selectedOpp, setSelectedOpp] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const { data: target, isLoading, error } = useQuery({
    queryKey: ['signal-scout-target', targetId, ensureAccount],
    queryFn: async () => {
      try {
        return await apiRequest<Target>(`/api/v1/signal-scout/targets/${targetId}`)
      } catch (e) {
        if (e instanceof ApiError && e.status === 404 && ensureAccount) {
          await apiRequest<Target>(`/api/v1/signal-scout/targets`, {
            method: 'POST',
            body: JSON.stringify({ account_id: ensureAccount }),
          })
          return apiRequest<Target>(`/api/v1/signal-scout/targets/${targetId}`)
        }
        throw e
      }
    },
    enabled: !!targetId,
  })

  const { data: scan } = useQuery({
    queryKey: ['signal-scout-scan', scanId],
    queryFn: () => apiRequest<Scan>(`/api/v1/signal-scout/scans/${scanId}`),
    enabled: !!scanId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s === 'queued' || s === 'running' ? 500 : false
    },
  })

  const signals = useQuery({
    queryKey: ['signal-scout-signals', targetId],
    queryFn: () =>
      apiRequest<{ items: Signal[] }>(`/api/v1/signal-scout/targets/${targetId}/signals`),
    enabled: !!targetId && !!target,
  })

  const opportunities = useQuery({
    queryKey: ['signal-scout-opps', targetId],
    queryFn: () =>
      apiRequest<{ items: Opportunity[]; notice: string }>(
        `/api/v1/signal-scout/targets/${targetId}/opportunities`,
      ),
    enabled: !!targetId && !!target,
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
          `Scan complete · ${scan.signal_count} signals · ${scan.opportunity_count} potential opportunities`,
        )
        setTab(scan.opportunity_count > 0 ? 'opportunities' : 'signals')
      }
    }
  }, [scan?.status, scan?.signal_count, scan?.opportunity_count, qc, targetId])

  // Auto-select top opportunity when list loads
  useEffect(() => {
    const first = opportunities.data?.items?.[0]
    if (first && !selectedOpp) setSelectedOpp(first.opportunity_id)
  }, [opportunities.data, selectedOpp])

  const startScan = useMutation({
    mutationFn: () =>
      apiRequest<{ scan_id: string; status: string }>(
        `/api/v1/signal-scout/targets/${targetId}/scan`,
        { method: 'POST' },
      ),
    onSuccess: (d) => {
      setScanId(d.scan_id)
      setToast('Scan started — watching detect → validate → extract → correlate → score')
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
      setToast('Explanation ready — score unchanged (rules own the number).')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Explain failed'),
  })

  const scanning = scan?.status === 'queued' || scan?.status === 'running' || startScan.isPending
  const signalItems = signals.data?.items || []
  const oppItems = opportunities.data?.items || []
  const typeCounts = useMemo(() => {
    const map = new Map<string, number>()
    for (const s of signalItems) {
      map.set(s.signal_type, (map.get(s.signal_type) || 0) + 1)
    }
    return [...map.entries()].map(([type, count]) => ({ type, count }))
  }, [signalItems])
  const topScore = oppItems[0]?.score ?? 0
  const scanned = Boolean(target?.last_scanned_at) || signalItems.length > 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/signal-scout" className="text-sm text-navy-600 hover:underline">
            ← Signal Scout
          </Link>
          <h2 className="mt-2 flex items-center gap-2 text-2xl font-semibold text-neutral-900">
            <Radar className="size-6 text-navy-600" />
            {target?.name || 'Loading target…'}
          </h2>
          <p className="mt-1 text-sm text-neutral-500">
            {target?.account_id || 'Manual target'}
            {target?.website_url ? (
              <>
                {' · '}
                <a
                  href={target.website_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-navy-600 hover:underline"
                >
                  {target.website_url}
                </a>
              </>
            ) : null}
          </p>
        </div>
        <FictionalBadge />
      </div>

      <p className="rounded-md border border-navy-200 bg-navy-50 px-3 py-2 text-sm text-navy-800">
        Live scan: homepage → same-domain hubs (AI/rules) → robots/domain validate → extract 7
        signal types → correlate ≥2 → rules score (signal strength factors). AI explains only.
      </p>

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
                  {target.signal_on_file.classification || 'PUBLIC'} on file
                </span>
              )}
              <span className="text-xs text-neutral-500">
                Last scanned: {target.last_scanned_at?.slice(0, 19) || 'Never'}
              </span>
            </div>
            {target.signal_on_file?.title && (
              <p className="text-sm text-neutral-700">
                CRM already holds: <span className="font-medium">{target.signal_on_file.title}</span>
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={scanning}
                onClick={() => startScan.mutate()}
                className="rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {scanning ? 'Scanning…' : 'Scan now'}
              </button>
              {target.recovery_link && (
                <Link
                  to={target.recovery_link}
                  className="rounded-md border border-navy-300 bg-white px-3 py-2 text-sm text-navy-800 hover:bg-navy-50"
                >
                  Review in Lead Recovery
                </Link>
              )}
            </div>
          </section>

          {scan && <LiveScanPipeline scan={scan} />}

          {(scan?.page_outcomes?.length || 0) > 0 && (
            <section className="rounded-lg border border-neutral-200 bg-white p-4 space-y-3">
              <div className="flex flex-wrap items-end justify-between gap-2">
                <div>
                  <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                    Page hubs detected
                  </p>
                  <p className="mt-0.5 text-sm text-neutral-600">
                    Same-domain pages from the official site — validated before any signal is stored.
                  </p>
                </div>
                <p className="text-xs text-neutral-500">
                  {scan!.page_outcomes.filter((p) => p.status === 'ok').length} ok ·{' '}
                  {scan!.page_outcomes.length} total
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {HUB_ORDER.map((hub) => {
                  const hits = (scan?.page_outcomes || []).filter(
                    (p) => (p.page_category || p.page_type) === hub,
                  )
                  const ok = hits.some((h) => h.status === 'ok')
                  return (
                    <span
                      key={hub}
                      className={[
                        'rounded-md border px-2 py-1 text-[11px] font-medium capitalize',
                        ok
                          ? 'border-navy-300 bg-navy-50 text-navy-800'
                          : hits.length
                            ? 'border-amber-300 bg-amber-50 text-amber-900'
                            : 'border-neutral-200 bg-neutral-50 text-neutral-400',
                      ].join(' ')}
                    >
                      {hub.replaceAll('_', ' ')}
                      {hits.length ? ` · ${hits.length}` : ''}
                    </span>
                  )
                })}
              </div>
              <ul className="max-h-48 space-y-1.5 overflow-y-auto text-xs">
                {(scan?.page_outcomes || []).map((p, i) => (
                  <li
                    key={`${p.url}-${i}`}
                    className={[
                      'flex flex-wrap items-center gap-2 rounded-md border px-2 py-1.5',
                      statusTone(p.status),
                    ].join(' ')}
                  >
                    <span className="font-medium capitalize">
                      {(p.page_category || p.page_type || 'page').replaceAll('_', ' ')}
                    </span>
                    <span className="capitalize opacity-80">{p.status || '—'}</span>
                    <span className="min-w-0 flex-1 truncate text-neutral-700">
                      {p.title || p.url}
                    </span>
                    {p.url ? (
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-0.5 font-medium text-navy-700 hover:underline"
                      >
                        Open <ExternalLink className="size-3" />
                      </a>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Detection overview — always tied to this university target */}
          <section className="space-y-3">
            <div className="rounded-lg border border-navy-200 bg-navy-50/60 px-4 py-3">
              <p className="text-xs font-medium tracking-wide text-navy-600 uppercase">
                Institution target
              </p>
              <p className="mt-0.5 text-base font-semibold text-navy-950">
                {target.name}
              </p>
              <p className="mt-0.5 text-xs text-navy-800/80">
                {[target.account_id, hostFromUrl(target.website_url) || target.website_url]
                  .filter(Boolean)
                  .join(' · ')}
                {' · '}
                All charts and signals below belong to this university only.
              </p>
            </div>
            <PipelineStrip
              signalCount={signalItems.length}
              opportunityCount={oppItems.length}
              scanned={scanned}
            />
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="rounded-lg border border-neutral-200 bg-white p-4">
                <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                  Detection mix
                </p>
                <SignalTypeBars types={typeCounts} institution={target.name} />
              </div>
              <div className="rounded-lg border border-neutral-200 bg-white p-4">
                <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                  Top potential score
                </p>
                <p className="mt-1 text-center text-xs font-medium text-navy-800">
                  {target.name}
                </p>
                <ScoreDonut score={topScore} band={oppItems[0]?.score_band} />
                <p className="mt-1 text-center text-xs text-neutral-600">
                  {oppItems[0]?.title ||
                    (oppItems.length
                      ? 'Leading potential opportunity'
                      : 'Scan to form a scored opportunity')}
                </p>
                {oppItems[0] && (
                  <p className="mt-1 text-center text-[11px] text-neutral-500">
                    Band: {oppItems[0].score_band || '—'} · from {signalItems.length}{' '}
                    related signals
                  </p>
                )}
              </div>
              <div className="rounded-lg border border-neutral-200 bg-white p-4 space-y-3">
                <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                  Scout snapshot
                </p>
                <p className="text-sm font-medium text-neutral-800">{target.name}</p>
                <dl className="grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-md bg-navy-50 px-3 py-2">
                    <dt className="text-xs text-navy-600">Signals</dt>
                    <dd className="text-2xl font-semibold tabular-nums text-navy-900">
                      {signalItems.length}
                    </dd>
                  </div>
                  <div className="rounded-md bg-amber-50 px-3 py-2">
                    <dt className="text-xs text-amber-800">Potential opps</dt>
                    <dd className="text-2xl font-semibold tabular-nums text-amber-950">
                      {oppItems.length}
                    </dd>
                  </div>
                  <div className="rounded-md border border-neutral-100 px-3 py-2">
                    <dt className="text-xs text-neutral-500">Pages stored</dt>
                    <dd className="text-lg font-semibold tabular-nums text-neutral-900">
                      {(target.pages || []).length ||
                        scan?.page_outcomes?.length ||
                        0}
                    </dd>
                  </div>
                  <div className="rounded-md border border-neutral-100 px-3 py-2">
                    <dt className="text-xs text-neutral-500">Signal types</dt>
                    <dd className="text-lg font-semibold tabular-nums text-neutral-900">
                      {typeCounts.length}
                    </dd>
                  </div>
                  <div className="col-span-2 rounded-md border border-neutral-100 px-3 py-2 text-xs text-neutral-600">
                    Mix detail:{' '}
                    {typeCounts.length
                      ? typeCounts
                          .map((t) => `${t.type.replaceAll('_', ' ')} (${t.count})`)
                          .join(' · ')
                      : '—'}
                  </div>
                </dl>
              </div>
            </div>
            {typeCounts.length > 0 && (
              <div className="rounded-lg border border-neutral-200 bg-white p-4 sm:hidden">
                <SignalTypeDonut types={typeCounts} institution={target.name} />
              </div>
            )}
          </section>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setTab('signals')}
              className={[
                'rounded-md border px-3 py-1.5 text-sm font-medium',
                tab === 'signals'
                  ? 'border-navy-600 bg-navy-600 text-white'
                  : 'border-neutral-300 bg-white text-neutral-700 hover:bg-navy-50',
              ].join(' ')}
            >
              Detected signals ({signalItems.length})
            </button>
            <button
              type="button"
              onClick={() => setTab('opportunities')}
              className={[
                'rounded-md border px-3 py-1.5 text-sm font-medium',
                tab === 'opportunities'
                  ? 'border-navy-600 bg-navy-600 text-white'
                  : 'border-neutral-300 bg-white text-neutral-700 hover:bg-navy-50',
              ].join(' ')}
            >
              Potential opportunities ({oppItems.length})
            </button>
          </div>

          {tab === 'signals' && (
            <div className="space-y-3">
              <p className="text-sm text-neutral-600">
                Showing validated signals for{' '}
                <span className="font-semibold text-navy-900">{target.name}</span>
                {target.account_id ? (
                  <>
                    {' '}
                    <span className="text-neutral-500">({target.account_id})</span>
                  </>
                ) : null}
                . Each card is tied to this institution only.
              </p>
              {signalItems.length === 0 ? (
                <p className="rounded-lg border border-neutral-200 bg-white px-4 py-6 text-sm text-neutral-600">
                  No validated signals yet. Click <span className="font-medium">Scan now</span>.
                  Failed or robots-blocked pages never invent a signal.
                </p>
              ) : (
                signalItems.map((s, idx) => {
                  const evHost = hostFromUrl(s.evidence?.[0]?.url)
                  return (
                    <section
                      key={s.signal_id}
                      className="rounded-lg border border-neutral-200 bg-white p-4 space-y-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0 space-y-1.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-md bg-neutral-100 px-2 py-0.5 text-[11px] font-medium tabular-nums text-neutral-600">
                              #{idx + 1}
                            </span>
                            <TypeChip type={s.signal_type} />
                          </div>
                          <h3 className="text-sm font-semibold text-neutral-900">{s.title}</h3>
                          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-navy-800">
                            <span className="rounded-md border border-navy-200 bg-navy-50 px-2 py-0.5 font-medium">
                              {target.name}
                            </span>
                            {target.account_id && (
                              <span className="text-neutral-500">{target.account_id}</span>
                            )}
                            {evHost && (
                              <span className="text-neutral-500">Source host: {evHost}</span>
                            )}
                          </p>
                        </div>
                      </div>
                      {s.summary && (
                        <p className="text-sm leading-relaxed text-neutral-700">{s.summary}</p>
                      )}
                      <div>
                        <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                          Evidence · {target.name}
                        </p>
                        <ul className="mt-2 space-y-2">
                          {s.evidence.map((e) => (
                            <li
                              key={`${e.url}-${e.snippet.slice(0, 24)}`}
                              className="rounded-md border border-neutral-100 bg-neutral-50 p-3 text-sm"
                            >
                              <p className="text-neutral-800">“{e.snippet}”</p>
                              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
                                <span>
                                  Published: {e.published_date || 'unavailable'}
                                </span>
                                {hostFromUrl(e.url) && (
                                  <span className="font-medium text-neutral-600">
                                    {hostFromUrl(e.url)}
                                  </span>
                                )}
                                <a
                                  href={e.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 font-medium text-navy-600 hover:underline"
                                >
                                  Open source <ExternalLink className="size-3" />
                                </a>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </section>
                  )
                })
              )}
            </div>
          )}

          {tab === 'opportunities' && (
            <div className="space-y-4">
              <p className="text-sm text-neutral-600">
                Potential only for{' '}
                <span className="font-semibold text-navy-900">{target.name}</span>
                {target.account_id ? (
                  <span className="text-neutral-500"> · {target.account_id}</span>
                ) : null}
                . Rules own the number — AI explains, it does not change the score.
              </p>

              {oppItems.length === 0 ? (
                <p className="rounded-lg border border-neutral-200 bg-white px-4 py-6 text-sm text-neutral-600">
                  Need at least two validated related signals to form a potential opportunity.
                  Run Scan now first.
                </p>
              ) : (
                <>
                  {oppItems.length > 1 && (
                    <div className="flex gap-2 overflow-x-auto pb-1">
                      {oppItems.map((o) => (
                        <button
                          key={o.opportunity_id}
                          type="button"
                          onClick={() => setSelectedOpp(o.opportunity_id)}
                          className={[
                            'shrink-0 rounded-lg border px-3 py-2 text-left transition',
                            selectedOpp === o.opportunity_id
                              ? 'border-navy-500 bg-navy-50'
                              : 'border-neutral-200 bg-white hover:border-navy-300',
                          ].join(' ')}
                        >
                          <p className="text-lg font-semibold tabular-nums text-navy-900">
                            {o.score}
                          </p>
                          <p className="max-w-[160px] truncate text-[11px] text-neutral-500">
                            {o.score_band} · {(o.signal_types || []).length} types
                          </p>
                        </button>
                      ))}
                    </div>
                  )}

                  {oppDetail.data ? (
                    <section className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
                      <div className="border-b border-neutral-100 bg-gradient-to-r from-navy-50 via-white to-amber-50/40 px-5 py-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0 space-y-1">
                            <p className="text-[11px] font-medium tracking-wide text-navy-700 uppercase">
                              {target.name}
                              {target.account_id ? ` · ${target.account_id}` : ''}
                            </p>
                            <h3 className="text-lg font-semibold text-neutral-900">
                              {oppDetail.data.title}
                            </h3>
                            <div className="flex flex-wrap gap-1.5 pt-1">
                              <BandPill band={oppDetail.data.score_band} />
                              {(oppDetail.data.signal_types || []).map((t) => (
                                <TypeChip key={t} type={t} />
                              ))}
                            </div>
                          </div>
                          <button
                            type="button"
                            disabled={explain.isPending}
                            onClick={() => explain.mutate(oppDetail.data!.opportunity_id)}
                            className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                          >
                            <Sparkles className="size-4" />
                            {explain.isPending ? 'Explaining…' : 'Explain with AI'}
                          </button>
                        </div>
                      </div>

                      <div className="grid gap-0 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                        <div className="flex flex-col items-center justify-center gap-3 border-b border-neutral-100 px-5 py-6 lg:border-b-0 lg:border-r">
                          <ScoreDonut
                            score={oppDetail.data.score}
                            band={oppDetail.data.score_band}
                            size="lg"
                          />
                          <p className="max-w-sm text-center text-sm leading-relaxed text-neutral-600">
                            {oppDetail.data.summary}
                          </p>
                        </div>

                        <div className="space-y-2 px-5 py-5">
                          <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                            Factor contribution
                          </p>
                          <p className="text-[11px] text-neutral-500">
                            Each bar is points earned vs max for that factor. Empty bars mean 0 —
                            still counted in the rules model.
                          </p>
                          <FactorBars factors={oppDetail.data.factors || []} />
                        </div>
                      </div>

                      {(oppDetail.data.signals?.length || 0) > 0 && (
                        <div className="border-t border-neutral-100 bg-neutral-50/80 px-5 py-4">
                          <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                            Linked signals · {target.name}
                          </p>
                          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                            {oppDetail.data.signals!.map((s) => (
                              <li
                                key={s.signal_id}
                                className="rounded-lg border border-neutral-200 bg-white px-3 py-2.5"
                              >
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <TypeChip type={s.signal_type} />
                                </div>
                                <p className="mt-1.5 text-sm font-medium text-neutral-900">
                                  {s.title}
                                </p>
                                <p className="mt-0.5 text-[11px] text-navy-700">{target.name}</p>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {oppDetail.data.explanation && (
                        <div className="space-y-2 border-t border-indigo-100 bg-indigo-50/60 px-5 py-4 text-sm text-indigo-950">
                          <p className="text-xs font-medium tracking-wide text-indigo-700 uppercase">
                            AI explanation · score unchanged
                          </p>
                          {(oppDetail.data.explanation.facts || []).slice(0, 4).map((f) => (
                            <p key={f.text} className="text-xs">
                              <span className="font-medium uppercase text-indigo-700">
                                {f.layer}
                              </span>
                              {' — '}
                              {f.text}
                            </p>
                          ))}
                          <p>{oppDetail.data.explanation.interpretation?.text}</p>
                          <p className="text-xs">
                            Recommended action:{' '}
                            {oppDetail.data.explanation.recommended_action?.text}
                          </p>
                        </div>
                      )}
                    </section>
                  ) : (
                    <p className="text-sm text-neutral-500">Loading opportunity detail…</p>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
