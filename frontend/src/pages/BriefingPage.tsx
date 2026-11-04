import { useAuth } from '@clerk/react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowUpRight,
  Handshake,
  HelpCircle,
  Radar,
  RotateCcw,
  ShieldAlert,
} from 'lucide-react'
import { Link } from 'react-router'
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { apiRequest } from '../api/client'
import { BriefingInbox } from '../components/BriefingInbox'
import { env } from '../lib/env'

type Dashboard = {
  as_of_date: string
  pipeline_open_usd: number
  at_risk_usd: number
  at_risk_note: string
  recovery_eligible_count: number
  high_risk_count: number
  medium_risk_count?: number
  low_risk_count?: number
  high_risk_usd?: number
  medium_risk_usd?: number
  low_risk_usd?: number
  open_blocker_count: number
  won_pending_handoff_count: number
  briefing: Array<{
    account_id: string
    title: string
    reason: string
    recommended_action: string
    href: string
    score?: number | null
    priority?: string
  }>
  data_label: string
}

const NAVY = '#1E3A66'
const NAVY_MID = '#4E6B9B'
const AMBER = '#D97706'
const RED = '#DC2626'
const GREEN = '#059669'
const INDIGO = '#4A4FD1'
const NEUTRAL = '#E2E8F0'

function money(n: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n)
}

function scoreFromItem(item: Dashboard['briefing'][0]) {
  if (typeof item.score === 'number') return item.score
  const m = item.reason.match(/(\d+)/)
  return m ? Number(m[1]) : 0
}

export function BriefingPage() {
  const { getToken } = useAuth()
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => {
      await getToken()
      return apiRequest<Dashboard>('/api/v1/dashboard')
    },
  })

  if (isLoading) {
    return <p className="text-neutral-500">Loading briefing…</p>
  }
  if (error || !data) {
    return (
      <p className="text-red-600">
        Could not load dashboard. {error instanceof Error ? error.message : ''}
      </p>
    )
  }

  const healthyUsd = Math.max(0, data.pipeline_open_usd - data.at_risk_usd)
  const pipelineShare = [
    { name: 'Healthy open', value: healthyUsd, fill: NAVY },
    { name: 'At risk', value: data.at_risk_usd, fill: AMBER },
  ].filter((d) => d.value > 0)

  // CRM has high / medium / low on open+stalled — always show all three bands
  const riskBands = [
    {
      name: 'High',
      count: data.high_risk_count,
      usd: data.high_risk_usd ?? data.at_risk_usd,
      track: 'bg-red-50',
      bar: 'bg-red-500',
    },
    {
      name: 'Medium',
      count: data.medium_risk_count ?? 0,
      usd: data.medium_risk_usd ?? 0,
      track: 'bg-amber-50',
      bar: 'bg-amber-500',
    },
    {
      name: 'Low',
      count: data.low_risk_count ?? 0,
      usd: data.low_risk_usd ?? 0,
      track: 'bg-navy-50',
      bar: 'bg-navy-500',
    },
  ]
  const riskCountMax = Math.max(...riskBands.map((b) => b.count), 1)
  const riskUsdMax = Math.max(...riskBands.map((b) => b.usd), 1)

  const workload = [
    { name: 'Recovery', value: data.recovery_eligible_count, fill: AMBER, to: '/recovery' },
    { name: 'High risk', value: data.high_risk_count, fill: RED, to: '/risk' },
    { name: 'Blockers', value: data.open_blocker_count, fill: INDIGO, to: '/blockers' },
    { name: 'Handoffs', value: data.won_pending_handoff_count, fill: GREEN, to: '/handoff' },
  ]

  const attentionScores = data.briefing.map((item) => ({
    name: item.title.length > 18 ? `${item.title.slice(0, 16)}…` : item.title,
    full: item.title,
    score: scoreFromItem(item),
    account_id: item.account_id,
  }))

  const atRiskPct =
    data.pipeline_open_usd > 0
      ? Math.round((data.at_risk_usd / data.pipeline_open_usd) * 100)
      : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-neutral-900">Today&apos;s briefing</h2>
          <p className="mt-1 text-sm text-neutral-500">
            As of {data.as_of_date} · {data.data_label}
          </p>
        </div>
        <p className="rounded-md border border-navy-200 bg-navy-50 px-3 py-1.5 text-xs text-navy-800">
          Evidence-backed priorities · human approves every outbound action
        </p>
      </div>

      <BriefingInbox />

      {/* KPI strip */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Open pipeline"
          value={money(data.pipeline_open_usd)}
          accent="border-navy-500"
          hint="Open + stalled deals"
        />
        <KpiCard
          label="At-risk value"
          value={money(data.at_risk_usd)}
          accent="border-amber-500"
          hint={`${atRiskPct}% of open pipeline · not lost revenue`}
        />
        <KpiCard
          label="Recovery eligible"
          value={String(data.recovery_eligible_count)}
          accent="border-amber-600"
          hint="Lost / inactive may be worth reviewing"
          to="/recovery"
        />
        <KpiCard
          label="High risk deals"
          value={String(data.high_risk_count)}
          accent="border-red-500"
          hint="Open deals in high risk band"
          to="/risk"
        />
      </div>

      {/* Charts row */}
      <div className="grid gap-4 lg:grid-cols-3">
        <section className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm lg:col-span-1">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-[11px] font-semibold tracking-wide text-neutral-500 uppercase">
                Pipeline composition
              </p>
              <p className="mt-0.5 text-sm text-neutral-600">Healthy vs at-risk open value</p>
            </div>
          </div>
          <div className="relative mx-auto mt-2 h-44 w-full max-w-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pipelineShare}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={52}
                  outerRadius={72}
                  paddingAngle={2}
                  stroke="none"
                >
                  {pipelineShare.map((d) => (
                    <Cell key={d.name} fill={d.fill} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v) => money(Number(v))}
                  contentStyle={{
                    borderRadius: 8,
                    border: '1px solid #E2E8F0',
                    fontSize: 12,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <p className="text-lg font-semibold tabular-nums text-navy-900">{atRiskPct}%</p>
              <p className="text-[10px] text-neutral-500">at risk share</p>
            </div>
          </div>
          <ul className="mt-1 space-y-1.5 text-xs">
            {pipelineShare.map((d) => (
              <li key={d.name} className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 text-neutral-600">
                  <span className="size-2 rounded-full" style={{ background: d.fill }} />
                  {d.name}
                </span>
                <span className="font-medium tabular-nums text-navy-900">{money(d.value)}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm lg:col-span-1">
          <p className="text-[11px] font-semibold tracking-wide text-neutral-500 uppercase">
            Open deals by risk band
          </p>
          <p className="mt-0.5 text-sm text-neutral-600">
            Deal count and pipeline $ across high / medium / low
          </p>
          <ul className="mt-4 space-y-3.5">
            {riskBands.map((b) => (
              <li key={b.name}>
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className="font-semibold text-neutral-800">{b.name}</span>
                  <span className="tabular-nums text-neutral-600">
                    <span className="font-semibold text-navy-900">{b.count}</span> deals
                    <span className="text-neutral-400"> · </span>
                    {money(b.usd)}
                  </span>
                </div>
                <div className={`mt-1.5 h-2.5 overflow-hidden rounded-full ${b.track}`}>
                  <div
                    className={`h-full rounded-full ${b.bar} transition-all`}
                    style={{ width: `${Math.max(4, (b.count / riskCountMax) * 100)}%` }}
                    title={`${b.count} deals`}
                  />
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-neutral-100">
                  <div
                    className="h-full rounded-full bg-neutral-400/70"
                    style={{
                      width: `${Math.max(b.usd > 0 ? 4 : 0, (b.usd / riskUsdMax) * 100)}%`,
                    }}
                    title={`Pipeline value ${money(b.usd)}`}
                  />
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[11px] text-neutral-500">
            Thick bar = deal count · thin = pipeline ${' '}
            <span className="text-neutral-400">·</span> Total{' '}
            <span className="font-medium text-neutral-700">
              {riskBands.reduce((s, b) => s + b.count, 0)} open/stalled
            </span>
          </p>
        </section>

        <section className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm lg:col-span-1">
          <p className="text-[11px] font-semibold tracking-wide text-neutral-500 uppercase">
            Feature workload
          </p>
          <p className="mt-0.5 text-sm text-neutral-600">Where the rep should spend time next</p>
          <div className="mt-3 h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={workload}
                layout="vertical"
                margin={{ top: 4, right: 16, left: 4, bottom: 4 }}
              >
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={72}
                  tick={{ fontSize: 11, fill: '#334155' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: '#EEF2F8' }}
                  contentStyle={{
                    borderRadius: 8,
                    border: '1px solid #E2E8F0',
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={16}>
                  {workload.map((d) => (
                    <Cell key={d.name} fill={d.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      {/* Attention + score chart */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
        <section className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
          <div className="flex items-center justify-between gap-2 border-b border-neutral-100 px-4 py-3">
            <div>
              <h3 className="font-semibold text-neutral-900">Needs attention</h3>
              <p className="text-xs text-neutral-500">
                Highest open-deal risk scores — open for evidence and next action
              </p>
            </div>
            <Link
              to="/risk"
              className="inline-flex items-center gap-1 text-xs font-medium text-navy-600 hover:text-navy-800"
            >
              All risk <ArrowUpRight className="size-3.5" />
            </Link>
          </div>
          <ul className="divide-y divide-neutral-100">
            {data.briefing.length === 0 ? (
              <li className="px-4 py-8 text-sm text-neutral-500">No high-risk briefing items.</li>
            ) : (
              data.briefing.map((item) => {
                const score = scoreFromItem(item)
                return (
                  <li
                    key={item.account_id}
                    className="flex flex-wrap items-center gap-4 px-4 py-3.5 transition hover:bg-navy-50/40"
                  >
                    <div className="flex size-12 shrink-0 flex-col items-center justify-center rounded-lg bg-red-50 text-red-700">
                      <span className="text-lg font-semibold tabular-nums leading-none">{score}</span>
                      <span className="text-[9px] font-medium uppercase tracking-wide">risk</span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium text-neutral-900">{item.title}</p>
                        <span className="rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-700">
                          High
                        </span>
                        <span className="font-mono text-[11px] text-neutral-400">{item.account_id}</span>
                      </div>
                      <p className="mt-0.5 text-sm text-neutral-500">{item.reason}</p>
                      <p className="mt-1 text-sm text-navy-700">{item.recommended_action}</p>
                      <div className="mt-2 h-1.5 max-w-xs overflow-hidden rounded-full bg-neutral-100">
                        <div
                          className="h-full rounded-full bg-red-500"
                          style={{ width: `${Math.min(100, score)}%` }}
                        />
                      </div>
                    </div>
                    <Link
                      to={item.href}
                      className="inline-flex shrink-0 items-center gap-1 rounded-md bg-navy-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-navy-700"
                    >
                      Open
                    </Link>
                  </li>
                )
              })
            )}
          </ul>
        </section>

        <section className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
          <p className="text-[11px] font-semibold tracking-wide text-neutral-500 uppercase">
            Top attention scores
          </p>
          <p className="mt-0.5 text-sm text-neutral-600">Risk score for briefing institutions</p>
          {attentionScores.length === 0 ? (
            <p className="mt-8 text-center text-sm text-neutral-500">No scores to chart</p>
          ) : (
            <div className="mt-2 h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={attentionScores}
                  layout="vertical"
                  margin={{ top: 4, right: 20, left: 4, bottom: 4 }}
                >
                  <XAxis type="number" domain={[0, 100]} hide />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={100}
                    tick={{ fontSize: 11, fill: '#334155' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    cursor={{ fill: '#FEF2F2' }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.[0]) return null
                      const row = payload[0].payload as (typeof attentionScores)[0]
                      return (
                        <div className="rounded-md border border-neutral-200 bg-white px-3 py-2 text-xs shadow-sm">
                          <p className="font-medium text-neutral-900">{row.full}</p>
                          <p className="text-neutral-600">Risk score {row.score}/100</p>
                          <p className="font-mono text-neutral-400">{row.account_id}</p>
                        </div>
                      )
                    }}
                  />
                  <Bar dataKey="score" fill={RED} radius={[0, 4, 4, 0]} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      </div>

      {/* Feature shortcuts */}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <FeatureTile
          to="/recovery"
          icon={RotateCcw}
          title="Lead Recovery"
          detail={`${data.recovery_eligible_count} accounts may be worth reviewing`}
          tone="amber"
        />
        <FeatureTile
          to="/risk"
          icon={ShieldAlert}
          title="Risk Prioritizer"
          detail={`${data.high_risk_count} high-risk open deals`}
          tone="red"
        />
        <FeatureTile
          to="/blockers"
          icon={HelpCircle}
          title="Blocker Resolution"
          detail={`${data.open_blocker_count} open blockers on file`}
          tone="indigo"
        />
        <FeatureTile
          to="/handoff"
          icon={Handshake}
          title="Customer Handoff"
          detail={`${data.won_pending_handoff_count} won deals awaiting handoff`}
          tone="green"
        />
        {env.signalScoutFeature ? (
          <FeatureTile
            to="/signal-scout"
            icon={Radar}
            title="Signal Scout"
            detail="Public pre-RFP signals for target institutions"
            tone="navy"
            className="sm:col-span-2 lg:col-span-4"
          />
        ) : null}
      </section>
    </div>
  )
}

function KpiCard({
  label,
  value,
  accent,
  hint,
  to,
}: {
  label: string
  value: string
  accent: string
  hint?: string
  to?: string
}) {
  const inner = (
    <>
      <p className="text-[11px] font-semibold tracking-wide text-neutral-500 uppercase">{label}</p>
      <p className="mt-2 text-[28px] leading-8 font-semibold tabular-nums text-navy-800">{value}</p>
      {hint ? <p className="mt-2 text-xs text-neutral-500">{hint}</p> : null}
    </>
  )
  const cls = [
    'rounded-xl border border-neutral-200 border-l-4 bg-white p-4 shadow-sm',
    accent,
    to ? 'transition hover:border-navy-300 hover:shadow-md' : '',
  ].join(' ')
  return to ? (
    <Link to={to} className={cls}>
      {inner}
    </Link>
  ) : (
    <div className={cls}>{inner}</div>
  )
}

function FeatureTile({
  to,
  icon: Icon,
  title,
  detail,
  tone,
  className = '',
}: {
  to: string
  icon: typeof RotateCcw
  title: string
  detail: string
  tone: 'amber' | 'red' | 'indigo' | 'green' | 'navy'
  className?: string
}) {
  const tones = {
    amber: 'bg-amber-50 text-amber-800 border-amber-200',
    red: 'bg-red-50 text-red-800 border-red-200',
    indigo: 'bg-indigo-50 text-indigo-800 border-indigo-200',
    green: 'bg-green-50 text-green-800 border-green-200',
    navy: 'bg-navy-50 text-navy-800 border-navy-200',
  }
  return (
    <Link
      to={to}
      className={[
        'flex items-start gap-3 rounded-xl border bg-white p-4 shadow-sm transition hover:shadow-md',
        className,
      ].join(' ')}
    >
      <span className={`rounded-lg border p-2 ${tones[tone]}`}>
        <Icon className="size-4" />
      </span>
      <span className="min-w-0">
        <span className="flex items-center gap-1 font-semibold text-neutral-900">
          {title}
          <ArrowUpRight className="size-3.5 text-neutral-400" />
        </span>
        <span className="mt-0.5 block text-sm text-neutral-500">{detail}</span>
      </span>
    </Link>
  )
}
