import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { apiRequest } from '../../api/client'
import { FictionalBadge } from '../../components/FictionalBadge'

type RecoveryItem = {
  account_id: string
  account_name: string
  opportunity_name: string | null
  deal_status: string
  deal_value: number
  currency: string
  lost_reason: string | null
  inactivity_days: number | null
  recovery_eligibility: string | null
  signal_title: string | null
  signal_classification: string | null
  signal_source_url: string | null
  followup_message_status: string | null
  draft_subject_preview: string | null
}

type RecoveryList = {
  items: RecoveryItem[]
  total: number
}

function money(n: number, currency: string) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency || 'USD',
    maximumFractionDigits: 0,
  }).format(n)
}

export function RecoveryListPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['recovery'],
    queryFn: () => apiRequest<RecoveryList>('/api/v1/recovery'),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-neutral-900">Lost lead recovery</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Accounts that may be worth reviewing — evidence first, drafts you control.
          </p>
        </div>
        <FictionalBadge />
      </div>

      {isLoading && <p className="text-neutral-500">Loading recovery candidates…</p>}
      {error && (
        <p className="text-red-600">{error instanceof Error ? error.message : 'Failed to load'}</p>
      )}

      {data && (
        <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white">
          <div className="border-b border-neutral-100 px-4 py-2 text-xs text-neutral-500">
            {data.total} candidates · default sort puts verified public signals first
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-neutral-100 text-xs tracking-wide text-neutral-500 uppercase">
                <tr>
                  <th className="px-4 py-3 font-medium">Account</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Value</th>
                  <th className="px-4 py-3 font-medium">Days inactive</th>
                  <th className="px-4 py-3 font-medium">Lost reason</th>
                  <th className="px-4 py-3 font-medium">Signal</th>
                  <th className="px-4 py-3 font-medium">Eligibility</th>
                  <th className="px-4 py-3 font-medium">Draft</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {data.items.map((item) => (
                  <tr key={item.account_id} className="hover:bg-navy-50/60">
                    <td className="px-4 py-3">
                      <Link
                        to={`/recovery/${item.account_id}`}
                        className="font-medium text-navy-600 hover:text-navy-700"
                      >
                        {item.account_name}
                      </Link>
                      <p className="text-xs text-neutral-400">{item.account_id}</p>
                    </td>
                    <td className="px-4 py-3 capitalize text-neutral-700">{item.deal_status}</td>
                    <td className="px-4 py-3 text-neutral-700">
                      {money(item.deal_value, item.currency)}
                    </td>
                    <td className="px-4 py-3 text-neutral-700">{item.inactivity_days ?? '—'}</td>
                    <td className="max-w-[14rem] truncate px-4 py-3 text-neutral-600">
                      {item.lost_reason || '—'}
                    </td>
                    <td className="px-4 py-3">
                      {item.signal_classification === 'PUBLIC_VERIFIED' ? (
                        <span className="inline-flex rounded-md border border-amber-600/30 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                          Verified public
                        </span>
                      ) : (
                        <span className="text-neutral-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 capitalize text-neutral-700">
                      {item.recovery_eligibility || '—'}
                    </td>
                    <td className="px-4 py-3 capitalize text-neutral-600">
                      {item.followup_message_status || '—'}
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
