import { useMutation, useQuery } from '@tanstack/react-query'
import { Building2, Plus, Radar, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { apiRequest } from '../../api/client'
import { FictionalBadge } from '../../components/FictionalBadge'
import { PipelineStrip } from './ScoutCharts'

function targetIdForAccount(accountId: string) {
  return `tgt_${accountId.toLowerCase()}`
}

/** Always visible — page must not look empty while CRM search is in flight */
const DEMO_HEROES = [
  {
    account_id: 'ACC-0178',
    name: 'Arizona State University',
    blurb: 'Public AI / learning platform news on file',
  },
  {
    account_id: 'ACC-0180',
    name: 'California State University',
    blurb: 'System AI partnership announcement on file',
  },
  {
    account_id: 'ACC-0189',
    name: 'The Ohio State University',
    blurb: 'AI Fluency initiative on file',
  },
]

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
  const [q, setQ] = useState('')
  const [tab, setTab] = useState<'crm' | 'manual'>('crm')
  const [name, setName] = useState('')
  const [website, setWebsite] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const [searchKey, setSearchKey] = useState('')

  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ['signal-scout-search', searchKey],
    queryFn: () =>
      apiRequest<SearchPayload>(
        `/api/v1/signal-scout/targets/search?q=${encodeURIComponent(searchKey)}`,
      ),
    retry: 1,
    staleTime: 60_000,
  })

  useEffect(() => {
    for (const hit of (data?.crm || []).slice(0, 5)) {
      void apiRequest(`/api/v1/signal-scout/targets`, {
        method: 'POST',
        body: JSON.stringify({ account_id: hit.account_id }),
      }).catch(() => undefined)
    }
  }, [data?.crm])

  const addManual = useMutation({
    mutationFn: () =>
      apiRequest<{ target_id: string }>(`/api/v1/signal-scout/targets`, {
        method: 'POST',
        body: JSON.stringify({ name, website_url: website }),
      }),
    onSuccess: (d) => {
      setToast('Target created — open Scan now for public signals.')
      void refetch()
      navigate(`/signal-scout/${d.target_id}`)
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Invalid target'),
  })

  const crmHits = data?.crm || []
  const noCrmMatch = Boolean(searchKey && data && crmHits.length === 0 && !isFetching)

  const openAccount = (accountId: string) => {
    navigate(`/signal-scout/${targetIdForAccount(accountId)}?account=${accountId}`)
  }

  const recent = data?.recent || []

  const heroIds = useMemo(() => new Set(DEMO_HEROES.map((h) => h.account_id)), [])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-semibold text-neutral-900">
            <Radar className="size-6 text-navy-600" />
            Signal Scout
          </h2>
          <p className="mt-1 text-sm text-neutral-500">
            Public pre-RFP changes with citations — rules score potential opportunities.
          </p>
        </div>
        <FictionalBadge />
      </div>

      {/* Calm honesty note — not an error banner */}
      <p className="rounded-md border border-navy-200 bg-navy-50 px-3 py-2 text-sm text-navy-800">
        Potential ≠ pipeline. Every signal needs a public URL + snippet. The score is rules-only;
        AI explains, it does not invent evidence.
      </p>

      <PipelineStrip signalCount={0} opportunityCount={0} scanned={false} preview />
      <p className="text-xs text-neutral-500">
        Homepage discovery → validate hubs → extract 7 signal types → correlate → rules score
        (signal strength). AI explains only.
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
            'inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium',
            tab === 'crm'
              ? 'border-navy-600 bg-navy-600 text-white'
              : 'border-neutral-300 bg-white text-neutral-700 hover:bg-navy-50',
          ].join(' ')}
        >
          <Building2 className="size-3.5" />
          Search CRM
        </button>
        <button
          type="button"
          onClick={() => setTab('manual')}
          className={[
            'inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium',
            tab === 'manual'
              ? 'border-navy-600 bg-navy-600 text-white'
              : 'border-neutral-300 bg-white text-neutral-700 hover:bg-navy-50',
          ].join(' ')}
        >
          <Plus className="size-3.5" />
          Add target (not in CRM)
        </button>
      </div>

      {/* Instant demo path — never blocked by search spinner */}
      <section className="rounded-lg border border-neutral-200 bg-white p-4">
        <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
          Demo institutions (CRM · public signal on file)
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {DEMO_HEROES.map((h) => (
            <button
              key={h.account_id}
              type="button"
              onClick={() => openAccount(h.account_id)}
              className="rounded-lg border border-neutral-200 bg-neutral-50 p-3 text-left hover:border-navy-400 hover:bg-navy-50"
            >
              <p className="text-sm font-semibold text-neutral-900">{h.name}</p>
              <p className="mt-1 text-xs text-neutral-500">{h.account_id}</p>
              <p className="mt-2 text-xs text-navy-700">{h.blurb}</p>
              <p className="mt-2 text-xs font-medium text-navy-600">Open target →</p>
            </button>
          ))}
        </div>
      </section>

      {tab === 'crm' ? (
        <section className="space-y-3 rounded-lg border border-neutral-200 bg-white p-4">
          <p className="text-sm font-medium text-neutral-800">Search any CRM institution</p>
          <div className="flex flex-wrap gap-2">
            <div className="relative min-w-[16rem] flex-1">
              <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-neutral-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') setSearchKey(q.trim())
                }}
                placeholder="e.g. Georgia Tech, Mumbai, ACC-0181"
                className="w-full rounded-md border border-neutral-300 py-2 pr-3 pl-9 text-sm"
              />
            </div>
            <button
              type="button"
              onClick={() => setSearchKey(q.trim())}
              className="rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white"
            >
              Search
            </button>
          </div>

          {isFetching && searchKey !== '' && (
            <p className="text-sm text-neutral-500">Searching CRM…</p>
          )}

          {error && (
            <div className="rounded-md border border-neutral-300 bg-neutral-50 px-3 py-2 text-sm text-neutral-800">
              <p className="font-medium">
                {error instanceof Error ? error.message : 'Search failed'}
              </p>
              <p className="mt-1 text-xs text-neutral-600">
                Use a demo card above, or retry. If auth failed, refresh and sign in again.
              </p>
              <button
                type="button"
                onClick={() => void refetch()}
                className="mt-2 rounded-md border border-neutral-300 bg-white px-2 py-1 text-xs"
              >
                Retry
              </button>
            </div>
          )}

          {crmHits.length > 0 && (
            <ul className="divide-y divide-neutral-100">
              {crmHits.map((hit) => (
                <li
                  key={hit.account_id}
                  className="flex flex-wrap items-center justify-between gap-2 py-3"
                >
                  <div>
                    <p className="font-medium text-neutral-900">{hit.name}</p>
                    <p className="text-xs text-neutral-500">
                      {hit.account_id} · {hit.deal_status}
                      {hit.signal_on_file ? ' · PUBLIC signal on file' : ''}
                      {heroIds.has(hit.account_id) ? ' · demo hero' : ''}
                    </p>
                    {hit.signal_title && (
                      <p className="mt-1 text-xs text-neutral-600">{hit.signal_title}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => openAccount(hit.account_id)}
                    className="rounded-md border border-navy-600 bg-navy-50 px-3 py-1.5 text-sm text-navy-800 hover:bg-navy-100"
                  >
                    Open target
                  </button>
                </li>
              ))}
            </ul>
          )}

          {noCrmMatch && (
            <div className="rounded-md border border-navy-200 bg-navy-50 px-3 py-3 text-sm text-navy-900">
              <p className="font-medium">No CRM match for “{searchKey}”.</p>
              <p className="mt-1 text-xs">
                Add it as a manual target with an official HTTPS institution URL (prefer .edu).
              </p>
              <button
                type="button"
                onClick={() => {
                  setName(searchKey)
                  setTab('manual')
                }}
                className="mt-2 rounded-md bg-navy-600 px-3 py-1.5 text-xs font-medium text-white"
              >
                Add “{searchKey}” as new target
              </button>
            </div>
          )}
        </section>
      ) : (
        <section className="space-y-3 rounded-lg border border-neutral-200 bg-white p-4">
          <p className="text-sm font-medium text-neutral-800">Add institution not in CRM</p>
          <p className="text-sm text-neutral-600">
            Official HTTPS site only — no open crawl, no link shorteners. Scan uses allowlisted /
            fixture evidence; nothing is invented when a fetch fails.
          </p>
          <label className="block text-xs font-medium text-neutral-500 uppercase">
            Institution name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm normal-case"
            />
          </label>
          <label className="block text-xs font-medium text-neutral-500 uppercase">
            Official website URL
            <input
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              placeholder="https://www.example.edu"
              className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm normal-case"
            />
          </label>
          <button
            type="button"
            disabled={!name.trim() || !website.trim() || addManual.isPending}
            onClick={() => addManual.mutate()}
            className="rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {addManual.isPending ? 'Creating…' : 'Create target'}
          </button>
        </section>
      )}

      {recent.length > 0 && (
        <section className="rounded-lg border border-neutral-200 bg-white p-4">
          <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
            Recent scout targets
          </p>
          <ul className="mt-2 space-y-2">
            {recent.map((t) => (
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
                  {t.last_scanned_at
                    ? ` · scanned ${t.last_scanned_at.slice(0, 10)}`
                    : ' · never scanned'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
