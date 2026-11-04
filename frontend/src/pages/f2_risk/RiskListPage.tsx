import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { apiRequest } from '../../api/client'
import { FictionalBadge } from '../../components/FictionalBadge'

type RiskItem = {
  account_id: string
  account_name: string
  opportunity_name: string | null
  opportunity_stage: string | null
  deal_status: string
  deal_value: number
  currency: string
  revenue_risk_score: number
  risk_category: string
  top_reason: string | null
  inactivity_days: number | null
  expected_close_date: string | null
  blocker_category: string | null
  overdue_followup: boolean
  next_followup_date: string | null
}

type RiskList = {
  items: RiskItem[]
  total: number
  at_risk_usd: number
  at_risk_note: string
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

export function RiskListPage() {
  const [preset, setPreset] = useState<'needs_attention_today' | null>('needs_attention_today')
  const [band, setBand] = useState<'high' | 'medium' | 'low' | ''>('high')
  const [status, setStatus] = useState<'open' | 'stalled' | ''>('')

  const queryPath = useMemo(() => {
    const params = new URLSearchParams()
    if (preset) params.set('preset', preset)
    else if (band) params.set('band', band)
    if (status) params.set('deal_status', status)
    const qs = params.toString()
    return `/api/v1/risk${qs ? `?${qs}` : ''}`
  }, [preset, band, status])

  const { data, isLoading, error } = useQuery({
    queryKey: ['risk', queryPath],
    queryFn: () => apiRequest<RiskList>(queryPath),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-neutral-900">Revenue risk prioritizer</h2>
          <p className="mt-1 text-sm text-neutral-500">
            What needs attention on open opportunities — rules score, evidence first.
          </p>
        </div>
        <FictionalBadge />
      </div>

      <div className="rounded-lg border border-amber-600/20 bg-amber-50 px-4 py-3">
        <p className="text-sm font-semibold text-navy-800">
          At-risk pipeline: {money(data?.at_risk_usd ?? 0)}
        </p>
        <p className="mt-1 text-xs text-amber-800">
          {data?.at_risk_note || 'At-risk value is not lost revenue.'}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => {
            setPreset((p) => (p ? null : 'needs_attention_today'))
            if (!preset) setBand('')
          }}
          className={[
            'rounded-md border px-3 py-1.5 text-sm font-medium',
            preset
              ? 'border-navy-600 bg-navy-600 text-white'
              : 'border-neutral-300 bg-white text-neutral-700 hover:bg-navy-50',
          ].join(' ')}
        >
          Needs attention today
        </button>
        {(['high', 'medium', 'low', ''] as const).map((b) => (
          <button
            key={b || 'all'}
            type="button"
            disabled={!!preset}
            onClick={() => {
              setPreset(null)
              setBand(b)
            }}
            className={[
              'rounded-md border px-3 py-1.5 text-sm capitalize',
              !preset && band === b
                ? 'border-navy-600 bg-navy-50 text-navy-700'
                : 'border-neutral-300 bg-white text-neutral-600',
              preset ? 'opacity-40' : '',
            ].join(' ')}
          >
            {b || 'All bands'}
          </button>
        ))}
        <span className="mx-1 h-5 w-px bg-neutral-200" />
        {(['', 'open', 'stalled'] as const).map((s) => (
          <button
            key={s || 'both'}
            type="button"
            onClick={() => setStatus(s)}
            className={[
              'rounded-md border px-3 py-1.5 text-sm capitalize',
              status === s
                ? 'border-navy-600 bg-navy-50 text-navy-700'
                : 'border-neutral-300 bg-white text-neutral-600',
            ].join(' ')}
          >
            {s || 'Open + stalled'}
          </button>
        ))}
      </div>

      {isLoading && <p className="text-neutral-500">Loading risk candidates…</p>}
      {error && (
        <p className="text-red-600">{error instanceof Error ? error.message : 'Failed to load'}</p>
      )}

      {data && data.items.length === 0 && (
        <p className="rounded-lg border border-neutral-200 bg-white px-4 py-6 text-sm text-neutral-600">
          No high-risk open deals. Try Medium or All bands.
        </p>
      )}

      {data && data.items.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white">
          <div className="border-b border-neutral-100 px-4 py-2 text-xs text-neutral-500">
            {data.total} deals · sorted by risk score then value
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-neutral-100 text-xs tracking-wide text-neutral-500 uppercase">
                <tr>
                  <th className="px-4 py-3 font-medium">Account</th>
                  <th className="px-4 py-3 font-medium">Stage</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Value</th>
                  <th className="px-4 py-3 font-medium">Score</th>
                  <th className="px-4 py-3 font-medium">Band</th>
                  <th className="px-4 py-3 font-medium">Days inactive</th>
                  <th className="px-4 py-3 font-medium">Close</th>
                  <th className="px-4 py-3 font-medium">Blocker</th>
                  <th className="px-4 py-3 font-medium">Follow-up</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {data.items.map((item) => (
                  <tr key={item.account_id} className="hover:bg-navy-50/60">
                    <td className="px-4 py-3">
                      <Link
                        to={`/risk/${item.account_id}`}
                        className="font-medium text-navy-600 hover:text-navy-700"
                      >
                        {item.account_name}
                      </Link>
                      <p className="text-xs text-neutral-400">{item.account_id}</p>
                    </td>
                    <td className="max-w-[10rem] truncate px-4 py-3 text-neutral-600">
                      {item.opportunity_stage || '—'}
                    </td>
                    <td className="px-4 py-3 capitalize text-neutral-700">{item.deal_status}</td>
                    <td className="px-4 py-3 text-neutral-700">
                      {money(item.deal_value, item.currency)}
                    </td>
                    <td className="px-4 py-3 font-semibold text-navy-700">{item.revenue_risk_score}</td>
                    <td className="px-4 py-3">
                      <BandPill band={item.risk_category} />
                    </td>
                    <td className="px-4 py-3 text-neutral-700">{item.inactivity_days ?? '—'}</td>
                    <td className="px-4 py-3 text-neutral-600">{item.expected_close_date || '—'}</td>
                    <td className="px-4 py-3 text-neutral-600">{item.blocker_category || '—'}</td>
                    <td className="px-4 py-3">
                      {item.overdue_followup ? (
                        <span className="text-xs font-medium text-amber-700">Overdue</span>
                      ) : (
                        <span className="text-neutral-500">{item.next_followup_date || '—'}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
