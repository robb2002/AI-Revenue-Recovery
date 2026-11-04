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

const NAVY = '#1e3a66'
const NAVY_MID = '#4e6b9b'
const INDIGO = '#4a4fd1'
const AMBER = '#d97706'
const GREEN = '#059669'
const NEUTRAL = '#cbd5e1'
const PIE_COLORS = [NAVY, INDIGO, AMBER, GREEN, NAVY_MID, '#7f97be', '#5b62e3']

type Factor = {
  key: string
  label: string
  points: number
  max_points?: number
  detail?: string
}

export function PipelineStrip({
  signalCount,
  opportunityCount,
  scanned,
  preview = false,
}: {
  signalCount: number
  opportunityCount: number
  scanned: boolean
  /** Static “how it works” (home) vs live progress (target) */
  preview?: boolean
}) {
  const steps = [
    {
      id: 'detect',
      label: 'Detect',
      done: preview || scanned || signalCount > 0,
    },
    {
      id: 'validate',
      label: 'Validate evidence',
      done: preview || signalCount > 0,
    },
    {
      id: 'correlate',
      label: 'Correlate ≥2',
      done: preview || opportunityCount > 0,
    },
    {
      id: 'score',
      label: 'Rules score',
      done: preview || opportunityCount > 0,
    },
  ]
  return (
    <ol className="grid gap-2 sm:grid-cols-4">
      {steps.map((s, i) => (
        <li
          key={s.id}
          className={[
            'rounded-lg border px-3 py-2',
            s.done
              ? 'border-navy-300 bg-navy-50'
              : 'border-neutral-200 bg-white text-neutral-400',
          ].join(' ')}
        >
          <p className="text-[10px] font-medium tracking-wide uppercase">
            {preview ? `Stage ${i + 1}` : `Step ${i + 1}`}
          </p>
          <p className={['text-sm font-semibold', s.done ? 'text-navy-800' : ''].join(' ')}>
            {s.label}
          </p>
        </li>
      ))}
    </ol>
  )
}

type LiveScan = {
  status: string
  stage?: string | null
  progress_pct?: number
  signal_count?: number
  opportunity_count?: number
  page_outcomes?: Array<{ status?: string }>
  label?: string | null
  mode?: string
}

const LIVE_STEPS = [
  {
    id: 'resolve_hubs',
    label: 'Detect pages',
    stages: ['queued', 'resolve_hubs'],
    detail: (s: LiveScan) => {
      const n = s.page_outcomes?.length || 0
      return n ? `${n} candidate page${n === 1 ? '' : 's'}` : 'Reading homepage…'
    },
  },
  {
    id: 'validate_pages',
    label: 'Validate',
    stages: ['validate_pages', 'fetch'],
    detail: (s: LiveScan) => {
      const pages = s.page_outcomes || []
      const ok = pages.filter((p) => p.status === 'ok').length
      return pages.length ? `${ok} ok · ${pages.length} checked` : 'Domain + robots'
    },
  },
  {
    id: 'extract',
    label: 'Extract signals',
    stages: ['extract', 'validate_evidence'],
    detail: (s: LiveScan) => {
      const n = s.signal_count || 0
      return n ? `${n} validated signal${n === 1 ? '' : 's'}` : '7-type taxonomy'
    },
  },
  {
    id: 'correlate',
    label: 'Correlate',
    stages: ['correlate'],
    detail: (s: LiveScan) => {
      const n = s.opportunity_count || 0
      return n ? `${n} potential opp${n === 1 ? '' : 's'}` : 'Need ≥2 related'
    },
  },
  {
    id: 'score',
    label: 'Rules score',
    stages: ['completed'],
    detail: (s: LiveScan) =>
      s.status === 'completed'
        ? `${s.opportunity_count || 0} scored · ${s.signal_count || 0} signals`
        : 'Factors only',
  },
] as const

function stepState(
  stepIndex: number,
  stage: string,
  status: string,
): 'done' | 'active' | 'pending' | 'failed' {
  if (status === 'failed') {
    const activeIdx = LIVE_STEPS.findIndex((s) =>
      (s.stages as readonly string[]).includes(stage),
    )
    if (activeIdx === stepIndex) return 'failed'
    if (activeIdx > stepIndex) return 'done'
    return 'pending'
  }
  if (status === 'completed') return 'done'
  const order = ['queued', 'resolve_hubs', 'validate_pages', 'fetch', 'extract', 'validate_evidence', 'correlate', 'completed']
  const stageIdx = Math.max(0, order.indexOf(stage || 'queued'))
  const stepStageIdx = Math.min(
    ...LIVE_STEPS[stepIndex].stages.map((st) => {
      const i = order.indexOf(st)
      return i < 0 ? 99 : i
    }),
  )
  const nextStart =
    stepIndex + 1 < LIVE_STEPS.length
      ? Math.min(
          ...LIVE_STEPS[stepIndex + 1].stages.map((st) => {
            const i = order.indexOf(st)
            return i < 0 ? 99 : i
          }),
        )
      : 99
  if (stageIdx >= nextStart) return 'done'
  if (stageIdx >= stepStageIdx) return 'active'
  return 'pending'
}

/** Live scan progress: detect → validate → extract → correlate → score */
export function LiveScanPipeline({ scan }: { scan: LiveScan }) {
  const stage = scan.stage || 'queued'
  const status = scan.status || 'queued'
  const pct = Math.max(0, Math.min(100, scan.progress_pct || 0))
  const running = status === 'queued' || status === 'running'

  return (
    <section className="rounded-lg border border-navy-200 bg-white p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
            Scanning pipeline
          </p>
          <p className="mt-0.5 text-sm font-medium text-navy-900">
            {status === 'completed'
              ? 'Scan complete'
              : status === 'failed'
                ? 'Scan failed'
                : 'Scan in progress…'}
            {scan.mode ? ` · ${scan.mode}` : ''}
          </p>
        </div>
        <div className="text-right text-xs text-neutral-500">
          <p className="tabular-nums font-medium text-navy-800">{pct}%</p>
          {scan.label && <p className="max-w-[220px] truncate">{scan.label}</p>}
        </div>
      </div>

      <div className="h-2 overflow-hidden rounded bg-neutral-100">
        <div
          className={[
            'h-full rounded transition-all duration-500',
            status === 'failed' ? 'bg-red-500' : running ? 'bg-navy-500' : 'bg-green-600',
          ].join(' ')}
          style={{ width: `${pct}%` }}
        />
      </div>

      <ol className="grid gap-2 sm:grid-cols-5">
        {LIVE_STEPS.map((step, i) => {
          const state = stepState(i, stage, status)
          return (
            <li
              key={step.id}
              className={[
                'rounded-lg border px-2.5 py-2 transition',
                state === 'done'
                  ? 'border-green-600/30 bg-green-50'
                  : state === 'active'
                    ? 'border-navy-400 bg-navy-50 ring-1 ring-navy-200'
                    : state === 'failed'
                      ? 'border-red-400 bg-red-50'
                      : 'border-neutral-200 bg-neutral-50 text-neutral-400',
              ].join(' ')}
            >
              <p className="text-[10px] font-medium tracking-wide uppercase opacity-80">
                {i + 1}. {state === 'active' && running ? 'Now' : state}
              </p>
              <p
                className={[
                  'text-sm font-semibold',
                  state === 'pending' ? '' : 'text-navy-900',
                ].join(' ')}
              >
                {step.label}
              </p>
              <p className="mt-0.5 text-[11px] leading-snug text-neutral-600">
                {step.detail(scan)}
              </p>
            </li>
          )
        })}
      </ol>

      <dl className="grid grid-cols-3 gap-2 text-center text-sm">
        <div className="rounded-md bg-navy-50 px-2 py-1.5">
          <dt className="text-[10px] uppercase tracking-wide text-navy-600">Pages</dt>
          <dd className="text-lg font-semibold tabular-nums text-navy-900">
            {scan.page_outcomes?.length || 0}
          </dd>
        </div>
        <div className="rounded-md bg-indigo-50 px-2 py-1.5">
          <dt className="text-[10px] uppercase tracking-wide text-indigo-700">Signals</dt>
          <dd className="text-lg font-semibold tabular-nums text-indigo-950">
            {scan.signal_count || 0}
          </dd>
        </div>
        <div className="rounded-md bg-amber-50 px-2 py-1.5">
          <dt className="text-[10px] uppercase tracking-wide text-amber-800">Potential</dt>
          <dd className="text-lg font-semibold tabular-nums text-amber-950">
            {scan.opportunity_count || 0}
          </dd>
        </div>
      </dl>
    </section>
  )
}

export function ScoreDonut({
  score,
  band,
  size = 'md',
}: {
  score: number
  band?: string
  size?: 'sm' | 'md' | 'lg'
}) {
  const safe = Math.max(0, Math.min(100, score))
  const data = [
    { name: 'score', value: safe },
    { name: 'rest', value: 100 - safe },
  ]
  const b = (band || '').toLowerCase()
  const fill =
    b === 'high' ? '#b45309' : b === 'medium' ? AMBER : b === 'low' ? NAVY_MID : NAVY
  const dim = size === 'lg' ? 176 : size === 'sm' ? 112 : 148
  const inner = size === 'lg' ? 58 : size === 'sm' ? 36 : 48
  const outer = size === 'lg' ? 74 : size === 'sm' ? 48 : 64

  return (
    <div className="relative mx-auto" style={{ width: dim, height: dim }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            innerRadius={inner}
            outerRadius={outer}
            startAngle={90}
            endAngle={-270}
            stroke="none"
          >
            <Cell fill={fill} />
            <Cell fill={NEUTRAL} />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <p
          className={[
            'font-semibold tabular-nums text-navy-900',
            size === 'lg' ? 'text-4xl' : size === 'sm' ? 'text-xl' : 'text-3xl',
          ].join(' ')}
        >
          {safe}
        </p>
        <p className="text-[11px] text-neutral-500">/ 100 rules</p>
        {band && (
          <p className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-neutral-500">
            {band}
          </p>
        )}
      </div>
    </div>
  )
}

/** Full-label factor meters — zeros still show a track (correct vs truncated Recharts bars). */
export function FactorBars({ factors }: { factors: Factor[] }) {
  if (factors.length === 0) {
    return <p className="text-sm text-neutral-500">No score factors yet.</p>
  }

  return (
    <ul className="space-y-3">
      {factors.map((f) => {
        const max = Math.max(1, f.max_points || f.points || 1)
        const pct = Math.round((Math.max(0, f.points) / max) * 100)
        return (
          <li key={f.key || f.label}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="font-medium text-neutral-800">{f.label}</span>
              <span className="shrink-0 tabular-nums text-neutral-500">
                {f.points}
                <span className="text-neutral-400">/{max}</span>
              </span>
            </div>
            {f.detail && (
              <p className="mt-0.5 text-[11px] leading-snug text-neutral-500">{f.detail}</p>
            )}
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-neutral-100">
              <div
                className={[
                  'h-full rounded-full transition-all duration-500',
                  f.points <= 0 ? 'bg-transparent' : 'bg-navy-600',
                ].join(' ')}
                style={{ width: `${pct}%` }}
                title={`${f.points} of ${max}`}
              />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

export function SignalTypeDonut({
  types,
  institution,
}: {
  types: Array<{ type: string; count: number }>
  institution?: string
}) {
  if (types.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-neutral-500">
        No signals detected yet
      </div>
    )
  }
  const total = types.reduce((sum, t) => sum + t.count, 0) || 1
  const data = types.map((t) => ({
    name: t.type.replaceAll('_', ' '),
    value: t.count,
    pct: Math.round((t.count / total) * 100),
  }))
  return (
    <div className="w-full">
      {institution && (
        <p className="mb-1 text-center text-[11px] font-medium text-navy-700">
          For {institution}
        </p>
      )}
      <div className="mx-auto h-36 w-full max-w-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={38}
              outerRadius={58}
              paddingAngle={2}
            >
              {data.map((d, i) => (
                <Cell key={d.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) return null
                const row = payload[0].payload as (typeof data)[0]
                return (
                  <div className="rounded-md border border-neutral-200 bg-white px-3 py-2 text-xs shadow-sm">
                    <p className="font-medium capitalize text-neutral-900">{row.name}</p>
                    <p className="text-neutral-600">
                      {row.value} of {total} ({row.pct}%)
                    </p>
                  </div>
                )
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-1 space-y-1">
        {data.map((d, i) => (
          <li
            key={d.name}
            className="flex items-center justify-between gap-2 text-[11px] text-neutral-700"
          >
            <span className="flex min-w-0 items-center gap-1.5 capitalize">
              <span
                className="inline-block size-2 shrink-0 rounded-full"
                style={{ background: PIE_COLORS[i % PIE_COLORS.length] }}
              />
              <span className="truncate">{d.name}</span>
            </span>
            <span className="shrink-0 tabular-nums font-medium text-navy-800">
              {d.value} · {d.pct}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Horizontal bars of signal types — clearer than pie for counts */
export function SignalTypeBars({
  types,
  institution,
}: {
  types: Array<{ type: string; count: number }>
  institution?: string
}) {
  if (types.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-neutral-500">No signals detected yet</p>
    )
  }
  const rows = [...types]
    .sort((a, b) => b.count - a.count)
    .map((t) => ({
      name: t.type.replaceAll('_', ' '),
      count: t.count,
    }))
  const max = Math.max(...rows.map((r) => r.count), 1)

  return (
    <div className="w-full space-y-2">
      {institution && (
        <p className="text-[11px] font-medium text-navy-700">Signal mix · {institution}</p>
      )}
      <div className="h-[180px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 28, left: 4, bottom: 4 }}>
            <XAxis type="number" domain={[0, max]} hide />
            <YAxis
              type="category"
              dataKey="name"
              width={128}
              tick={{ fontSize: 11, fill: '#334155' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: '#eef2f8' }}
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) return null
                const row = payload[0].payload as (typeof rows)[0]
                return (
                  <div className="rounded-md border border-neutral-200 bg-white px-3 py-2 text-xs shadow-sm">
                    <p className="font-medium capitalize text-neutral-900">{row.name}</p>
                    <p className="text-neutral-600">{row.count} signal(s) for this institution</p>
                  </div>
                )
              }}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={14} fill={NAVY} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
