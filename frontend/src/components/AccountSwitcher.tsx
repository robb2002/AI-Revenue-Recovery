import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router'
import { apiRequest } from '../api/client'
import { getWorkspaceAccountId, setWorkspaceAccountId } from '../lib/workspaceAccount'

type AccountRow = {
  account_id: string
  account_name: string
  opportunity_name?: string | null
  deal_status?: string | null
}

type AccountsPayload = {
  items: AccountRow[]
  total: number
}

export type WorkspaceFeature = 'meetings' | 'drafts' | 'blockers' | 'handoff'

type Props = {
  accountId?: string
  feature: WorkspaceFeature
  /** Soft demo hint ids (chip only — account is still user-selected) */
  demoAccountIds?: string[]
  className?: string
}

function pathFor(feature: WorkspaceFeature, accountId: string) {
  return `/accounts/${accountId}/${feature}`
}

export function AccountSwitcher({
  accountId,
  feature,
  demoAccountIds = ['ACC-0181'],
  className = '',
}: Props) {
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({
    queryKey: ['accounts', 'switcher'],
    queryFn: () => apiRequest<AccountsPayload>('/api/v1/accounts?limit=100'),
    staleTime: 60_000,
  })

  const items = data?.items ?? []

  const resolvedId = useMemo(() => {
    if (accountId && items.some((a) => a.account_id === accountId)) return accountId
    const saved = getWorkspaceAccountId()
    if (saved && items.some((a) => a.account_id === saved)) return saved
    const demo = demoAccountIds.find((id) => items.some((a) => a.account_id === id))
    if (demo) return demo
    return items[0]?.account_id ?? null
  }, [accountId, items, demoAccountIds])

  useEffect(() => {
    if (!resolvedId) return
    setWorkspaceAccountId(resolvedId)
    if (!accountId) {
      navigate(pathFor(feature, resolvedId), { replace: true })
    }
  }, [resolvedId, accountId, feature, navigate])

  const current = items.find((a) => a.account_id === resolvedId)

  return (
    <div
      className={[
        'flex flex-wrap items-end gap-3 rounded-xl border border-neutral-200 bg-white px-4 py-3 shadow-sm',
        className,
      ].join(' ')}
    >
      <div className="min-w-[16rem] flex-1">
        <label className="text-[11px] font-semibold tracking-wide text-neutral-500 uppercase">
          Working account
        </label>
        {isLoading ? (
          <p className="mt-1 text-sm text-neutral-400">Loading CRM accounts…</p>
        ) : (
          <select
            className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900"
            value={resolvedId || ''}
            onChange={(e) => {
              const id = e.target.value
              setWorkspaceAccountId(id)
              navigate(pathFor(feature, id))
            }}
          >
            {items.map((a) => (
              <option key={a.account_id} value={a.account_id}>
                {a.account_name} ({a.account_id})
                {a.deal_status ? ` · ${a.deal_status}` : ''}
              </option>
            ))}
          </select>
        )}
      </div>
      <div className="pb-1 text-xs text-neutral-500">
        {current?.opportunity_name ? (
          <p className="max-w-md truncate" title={current.opportunity_name}>
            {current.opportunity_name}
          </p>
        ) : (
          <p>Select any CRM account — not locked to one institution</p>
        )}
        {resolvedId && demoAccountIds.includes(resolvedId) && feature === 'meetings' && (
          <p className="mt-0.5 font-medium text-amber-700">
            Demo transcript sample available for this account
          </p>
        )}
      </div>
    </div>
  )
}
