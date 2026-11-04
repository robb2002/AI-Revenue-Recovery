import { useMutation, useQuery } from '@tanstack/react-query'
import { Radar } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { apiRequest } from '../../api/client'
import { FictionalBadge } from '../../components/FictionalBadge'

type CrmHit = {
  account_id: string
  name: string
  deal_status: string
  website_url: string | null
  signal_on_file: boolean
  signal_title: string | null
  signal_classification: string | null
  recovery_eligibility: string | null
}

type TargetRow = {
  target_id: string
  account_id: string | null
  name: string
  website_url: string
  source: string
  last_scanned_at: string | null
}

type SearchPayload = {
  crm: CrmHit[]
  manual: TargetRow[]
  recent: TargetRow[]
  notice: string
}

export function SignalScoutHomePage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('Arizona State')
  const [tab, setTab] = useState<'crm' | 'manual'>('crm')
  const [name, setName] = useState('')
  const [website, setWebsite] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const [searchKey, setSearchKey] = useState('Arizona State')

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ['signal-scout-search', searchKey],
    queryFn: () =>
      apiRequest<SearchPayload>(
        `/api/v1/signal-scout/targets/search?q=${encodeURIComponent(searchKey)}`,
      ),
    retry: 1,
    staleTime: 30_000,
  })

  const openCrm = useMutation({
    mutationFn: (accountId: string) =>
      apiRequest<{ target_id: string }>(`/api/v1/signal-scout/targets`, {
        method: 'POST',
        body: JSON.stringify({ account_id: accountId }),
      }),
    onSuccess: (d) => navigate(`/signal-scout/${d.target_id}`),
    onError: (e) => setToast(e instanceof Error ? e.message : 'Could not open target'),
  })

  const addManual = useMutation({
    mutationFn: () =>
      apiRequest<{ target_id: string }>(`/api/v1/signal-scout/targets`, {
        method: 'POST',
        body: JSON.stringify({ name, website_url: website }),
      }),
    onSuccess: (d) => {
      setToast('Manual target created.')
      void refetch()
      navigate(`/signal-scout/${d.target_id}`)
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Invalid target'),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-semibold text-neutral-900">
            <Radar className="size-6 text-amber-700" />
            Signal Scout
          </h2>
          <p className="mt-1 text-sm text-neutral-500">
            Find what changed publicly before an RFP — citations, not hunches.
          </p>
        </div>
        <FictionalBadge />
      </div>

      <p className="rounded-md border border-amber-600/20 bg-amber-50 px-3 py-2 text-sm text-amber-950">
        {data?.notice ||
          'Potential opportunities are not pipeline. Public sources only; no invented signals.'}
      </p>

      {toast && (
        <div className="rounded-md border border-green-600/30 bg-green-50 px-4 py-2 text-sm text-green-700">
          {toast}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setTab('crm')}
          className={[
            'cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium',
            tab === 'crm'
              ? 'border-navy-600 bg-navy-600 text-white'
              : 'border-neutral-300 bg-white text-neutral-700 hover:bg-navy-50',
          ].join(' ')}
        >
          From CRM
        </button>
        <button
          type="button"
          onClick={() => setTab('manual')}
          className={[
            'cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium',
            tab === 'manual'
              ? 'border-navy-600 bg-navy-600 text-white'
              : 'border-neutral-300 bg-white text-neutral-700 hover:bg-navy-50',
          ].join(' ')}
        >
          Add target
        </button>
      </div>

      {tab === 'crm' ? (
        <section className="space-y-3 rounded-lg border border-neutral-200 bg-white p-4">
          <div className="flex flex-wrap gap-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') setSearchKey(q.trim())
              }}
              placeholder="Search institution name or account id"
              className="min-w-[16rem] flex-1 rounded-md border border-neutral-300 px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() => setSearchKey(q.trim())}
              className="cursor-pointer rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white"
            >
              Search
            </button>
          </div>
          <p className="text-xs text-neutral-500">
            Demo heroes: Arizona State (ACC-0178), California State (ACC-0180), Ohio State
            (ACC-0189).
          </p>
          {(isLoading || isFetching) && (
            <p className="text-sm text-neutral-500">Searching…</p>
          )}
          {error && (
            <div className="rounded-md border border-red-600/30 bg-red-50 px-3 py-2 text-sm text-red-700">
              <p className="font-medium">
                {error instanceof Error ? error.message : 'Search failed'}
              </p>
              <p className="mt-1 text-xs">
                If this says authentication failed: refresh the page and sign in again. Clerk key
                fetch can time out on a slow network — retry once.
              </p>
              <button
                type="button"
                onClick={() => void refetch()}
                className="mt-2 cursor-pointer rounded-md border border-red-600/40 bg-white px-2 py-1 text-xs text-red-800"
              >
                Retry search
              </button>
            </div>
          )}
          <ul className="divide-y divide-neutral-100">
            {(data?.crm || []).map((hit) => (
              <li key={hit.account_id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div>
                  <p className="font-medium text-neutral-900">{hit.name}</p>
                  <p className="text-xs text-neutral-500">
                    {hit.account_id} · {hit.deal_status}
                    {hit.signal_on_file ? ' · public signal on file' : ''}
                  </p>
                  {hit.signal_title && (
                    <p className="mt-1 text-xs text-neutral-600">{hit.signal_title}</p>
                  )}
                </div>
                <button
                  type="button"
                  disabled={openCrm.isPending}
                  onClick={() => openCrm.mutate(hit.account_id)}
                  className="cursor-pointer rounded-md border border-navy-600 bg-navy-50 px-3 py-1.5 text-sm text-navy-800"
                >
                  Open target
                </button>
              </li>
            ))}
          </ul>
          {data && data.crm.length === 0 && (
            <p className="text-sm text-neutral-500">No CRM matches. Try Add target.</p>
          )}
        </section>
      ) : (
        <section className="space-y-3 rounded-lg border border-neutral-200 bg-white p-4">
          <p className="text-sm text-neutral-600">
            Official HTTPS institution URL only (prefer .edu). No open web crawl.
          </p>
          <label className="block text-xs font-medium text-neutral-500 uppercase">
            Name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-xs font-medium text-neutral-500 uppercase">
            Website URL
            <input
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              placeholder="https://www.example.edu"
              className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
            />
          </label>
          <button
            type="button"
            disabled={!name.trim() || !website.trim() || addManual.isPending}
            onClick={() => addManual.mutate()}
            className="cursor-pointer rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Create target
          </button>
        </section>
      )}

      {(data?.recent || []).length > 0 && (
        <section className="rounded-lg border border-neutral-200 bg-white p-4">
          <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">Recent targets</p>
          <ul className="mt-2 space-y-2">
            {data!.recent.map((t) => (
              <li key={t.target_id}>
                <Link
                  to={`/signal-scout/${t.target_id}`}
                  className="text-sm font-medium text-navy-700 hover:underline"
                >
                  {t.name}
                </Link>
                <span className="text-xs text-neutral-400">
                  {' '}
                  · {t.source}
                  {t.last_scanned_at ? ` · scanned ${t.last_scanned_at.slice(0, 10)}` : ' · never scanned'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
