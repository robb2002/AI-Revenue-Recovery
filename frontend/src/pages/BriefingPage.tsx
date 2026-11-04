import { useAuth } from '@clerk/react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { apiRequest } from '../api/client'

type Dashboard = {
  as_of_date: string
  pipeline_open_usd: number
  at_risk_usd: number
  at_risk_note: string
  recovery_eligible_count: number
  high_risk_count: number
  open_blocker_count: number
  won_pending_handoff_count: number
  briefing: Array<{
    account_id: string
    title: string
    reason: string
    recommended_action: string
    href: string
  }>
  data_label: string
}

function money(n: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n)
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

  const cards = [
    { label: 'Open pipeline', value: money(data.pipeline_open_usd) },
    { label: 'At-risk value', value: money(data.at_risk_usd), note: data.at_risk_note },
    { label: 'Recovery eligible', value: String(data.recovery_eligible_count) },
    { label: 'High risk deals', value: String(data.high_risk_count) },
  ]

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-semibold text-neutral-900">Today&apos;s briefing</h2>
        <p className="mt-1 text-sm text-neutral-500">As of {data.as_of_date} · {data.data_label}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((c) => (
          <div key={c.label} className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">{c.label}</p>
            <p className="mt-2 text-2xl font-semibold text-navy-600">{c.value}</p>
            {'note' in c && c.note ? (
              <p className="mt-2 text-xs text-amber-700">{c.note}</p>
            ) : null}
          </div>
        ))}
      </div>

      <section className="rounded-lg border border-neutral-200 bg-white">
        <div className="border-b border-neutral-100 px-4 py-3">
          <h3 className="font-semibold text-neutral-900">Needs attention</h3>
        </div>
        <ul className="divide-y divide-neutral-100">
          {data.briefing.length === 0 ? (
            <li className="px-4 py-6 text-sm text-neutral-500">No high-risk briefing items.</li>
          ) : (
            data.briefing.map((item) => (
              <li key={item.account_id} className="flex items-start justify-between gap-4 px-4 py-3">
                <div>
                  <p className="font-medium text-neutral-900">{item.title}</p>
                  <p className="text-sm text-neutral-500">{item.reason}</p>
                  <p className="mt-1 text-sm text-navy-600">{item.recommended_action}</p>
                </div>
                <Link
                  to={item.href}
                  className="shrink-0 text-sm font-medium text-navy-600 hover:text-navy-700"
                >
                  Open
                </Link>
              </li>
            ))
          )}
        </ul>
      </section>
    </div>
  )
}
