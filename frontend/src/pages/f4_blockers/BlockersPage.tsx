import { useMutation, useQuery } from '@tanstack/react-query'
import { HelpCircle, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { apiRequest } from '../../api/client'
import { FictionalBadge } from '../../components/FictionalBadge'

type BlockerPayload = {
  account_id: string
  account_name: string
  blocker: {
    detected: boolean
    category: string | null
    description: string | null
    severity: string | null
    status: string | null
    deadline: string | null
    supporting_document_reference: string | null
    suggested_resolution: string | null
  }
  starter_questions: string[]
  as_of_date: string
}

type Citation = {
  doc_id: string
  title: string
  snippet: string
  source_url?: string | null
  section?: string
}

type Answer = {
  answer_id: string
  question: string
  answer_status: 'answered' | 'partially_answered' | 'insufficient_evidence'
  answer_text: string
  citations: Citation[]
  missing: string[]
  recommended_action?: string
  model_called: boolean
  notice: string
  state: string
}

function startersForCategory(category: string | null | undefined): string[] {
  const cat = (category || '').toLowerCase()
  if (cat.includes('integration')) {
    return [
      "Does Pearson's LMS integration work with Brightspace (D2L)?",
      'Can grades go from MyLab back into our LMS gradebook?',
      'Will grades flow from our LMS into MyLab as well?',
    ]
  }
  if (cat.includes('security')) {
    return [
      'Is the product SOC 2 or ISO 27001 certified?',
      'Where will our student data be hosted?',
      'Can we use SAML or OpenID Connect single sign-on?',
    ]
  }
  if (cat.includes('budget') || cat.includes('pricing')) {
    return [
      'What is the discount for 5,000 learners over three years?',
      'Is the courseware accessible, and can we get a VPAT?',
    ]
  }
  if (cat.includes('procurement')) {
    return [
      'What documents does procurement typically need from Pearson?',
      'Who provides SOC 2, ISO, and accessibility (VPAT) paperwork?',
      'Is there a checklist for vendor registration and tender packages?',
    ]
  }
  return [
    "Does Pearson's LMS integration work with Brightspace (D2L)?",
    'Can grades go from MyLab back into our LMS gradebook?',
    'What is the discount for 5,000 learners over three years?',
  ]
}

function StatusPill({ status }: { status: Answer['answer_status'] }) {
  const styles =
    status === 'answered'
      ? 'border-green-600/40 bg-green-50 text-green-700'
      : status === 'partially_answered'
        ? 'border-amber-600/40 bg-amber-50 text-amber-800'
        : 'border-navy-300 bg-navy-50 text-navy-800'
  const label =
    status === 'answered'
      ? 'answered'
      : status === 'partially_answered'
        ? 'partially answered'
        : 'insufficient evidence'
  return (
    <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${styles}`}>
      {label}
    </span>
  )
}

export function BlockersPage() {
  const { accountId: routeId } = useParams()
  const accountId = routeId || 'ACC-0181'
  const [searchParams, setSearchParams] = useSearchParams()
  const autoAsk = searchParams.get('ask') === '1'
  const categoryFromRisk = searchParams.get('category') || ''
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const autoAsked = useRef(false)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['blocker', accountId],
    queryFn: () => apiRequest<BlockerPayload>(`/api/v1/accounts/${accountId}/blocker`),
    staleTime: 60_000,
  })

  const starters = useMemo(() => {
    if (data?.starter_questions?.length) return data.starter_questions
    return startersForCategory(categoryFromRisk || data?.blocker.category)
  }, [data, categoryFromRisk])

  const ask = useMutation({
    mutationFn: (q: string) =>
      apiRequest<Answer>(`/api/v1/accounts/${accountId}/blocker/answer`, {
        method: 'POST',
        body: JSON.stringify({ question: q }),
      }),
    onSuccess: (d) => {
      setAnswer(d)
      setToast('New draft created. Approve or Reject this version (nothing is sent).')
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Ask failed'),
  })

  useEffect(() => {
    autoAsked.current = false
    setAnswer(null)
    setQuestion('')
    setToast(null)
  }, [accountId])

  // Risk deep-link: ask immediately from category starters — do not wait on GET
  useEffect(() => {
    if (!autoAsk || autoAsked.current || ask.isPending) return
    const suggested = data?.blocker.suggested_resolution?.trim()
    const q =
      (suggested && suggested.includes('?') ? suggested : null) ||
      starters[0] ||
      ''
    if (!q) return
    autoAsked.current = true
    setQuestion(q)
    setToast('Opened from Risk — drafting an answer for this blocker…')
    ask.mutate(q)
    setSearchParams({}, { replace: true })
  }, [autoAsk, starters, data, ask.isPending, ask.mutate, setSearchParams])

  const approve = useMutation({
    mutationFn: () =>
      apiRequest<{ notice: string; state: string }>(
        `/api/v1/blocker-answers/${answer!.answer_id}/approve`,
        { method: 'POST' },
      ),
    onMutate: () => {
      setAnswer((a) =>
        a
          ? {
              ...a,
              state: 'approved',
              notice: 'Approved for salesperson use. Nothing was sent.',
            }
          : a,
      )
      setToast('Approved for salesperson use. Nothing was sent.')
    },
    onError: (e) => {
      setAnswer((a) => (a ? { ...a, state: 'draft' } : a))
      setToast(e instanceof Error ? e.message : 'Approve failed')
    },
  })

  const reject = useMutation({
    mutationFn: () =>
      apiRequest<{ notice: string; state: string }>(
        `/api/v1/blocker-answers/${answer!.answer_id}/reject`,
        { method: 'POST' },
      ),
    onMutate: () => {
      setAnswer((a) =>
        a
          ? { ...a, state: 'rejected', notice: 'Rejected. Draft not ready to share.' }
          : a,
      )
      setToast('Rejected. Draft not ready to share.')
    },
    onError: (e) => {
      setAnswer((a) => (a ? { ...a, state: 'draft' } : a))
      setToast(e instanceof Error ? e.message : 'Reject failed')
    },
  })

  const categoryLabel = data?.blocker.category || categoryFromRisk || '—'
  const severityLabel = data?.blocker.severity || '—'
  const statusLabel = data?.blocker.status || '—'

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/knowledge" className="text-sm text-navy-600 hover:underline">
            Knowledge base →
          </Link>
          <h2 className="mt-2 flex items-center gap-2 text-2xl font-semibold text-neutral-900">
            <HelpCircle className="size-6 text-navy-600" />
            Deal blocker resolution
          </h2>
          <p className="mt-1 text-sm text-neutral-500">
            {data?.account_name || accountId} · answers from approved docs only
          </p>
        </div>
        <FictionalBadge />
      </div>

      {toast && (
        <div className="rounded-md border border-green-600/30 bg-green-50 px-4 py-2 text-sm text-green-700">
          {toast}
        </div>
      )}

      {isError && (
        <p className="text-red-600">{error instanceof Error ? error.message : 'Failed to load'}</p>
      )}

      <section className="rounded-lg border border-neutral-200 bg-white p-4">
        <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">Open blocker</p>
        <div className="mt-2 flex flex-wrap gap-2 text-sm">
          <span className="rounded-md bg-amber-50 px-2 py-0.5 text-amber-800">{categoryLabel}</span>
          <span className="rounded-md bg-neutral-100 px-2 py-0.5 text-neutral-700">
            {severityLabel} · {statusLabel}
          </span>
        </div>
        {isLoading && !data ? (
          <p className="mt-3 text-sm text-neutral-500">Loading blocker details…</p>
        ) : (
          <>
            <p className="mt-3 text-sm text-neutral-800">
              {data?.blocker.description || 'Blocker context from CRM — ask below for a cited draft.'}
            </p>
            {data?.blocker.supporting_document_reference && (
              <p className="mt-2 text-xs text-neutral-500">
                Supporting doc hint: {data.blocker.supporting_document_reference}
              </p>
            )}
          </>
        )}
      </section>

      <section className="rounded-lg border border-neutral-200 bg-white p-4 space-y-3">
        <h3 className="text-sm font-semibold text-neutral-900">Ask from approved knowledge</h3>
        <div className="flex flex-wrap gap-2">
          {starters.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => {
                setQuestion(q)
                ask.mutate(q)
              }}
              className="cursor-pointer rounded-md border border-neutral-300 bg-neutral-50 px-2.5 py-1 text-xs text-neutral-700 hover:bg-navy-50"
            >
              {q}
            </button>
          ))}
        </div>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          className="w-full rounded-md border border-neutral-300 p-3 text-sm"
          placeholder="Customer question…"
        />
        <button
          type="button"
          disabled={!question.trim() || ask.isPending}
          onClick={() => ask.mutate(question)}
          className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Sparkles className="size-4" />
          {ask.isPending ? 'Retrieving docs…' : 'Ask'}
        </button>
        {ask.isPending && (
          <p className="text-xs text-neutral-500">
            Drafting from approved knowledge for this blocker…
          </p>
        )}
      </section>

      {answer && (
        <section className="rounded-lg border border-neutral-200 bg-white p-4 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-neutral-900">Draft answer</h3>
            <div className="flex items-center gap-2">
              <StatusPill status={answer.answer_status} />
              {answer.state === 'approved' && (
                <span className="rounded-md border border-green-600/30 bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                  Approved
                </span>
              )}
              {answer.state === 'rejected' && (
                <span className="rounded-md border border-neutral-300 bg-neutral-50 px-2 py-0.5 text-xs font-medium text-neutral-600">
                  Rejected
                </span>
              )}
            </div>
          </div>
          <p className="text-xs text-neutral-500">{answer.question}</p>
          <p className="text-base leading-relaxed text-neutral-900">{answer.answer_text}</p>

          {answer.answer_status === 'insufficient_evidence' && (
            <div className="rounded-md border border-navy-200 bg-navy-50 px-3 py-2 text-sm text-navy-800">
              <p className="font-medium">Insufficient evidence in approved docs</p>
              <p className="mt-1 text-xs">Do not invent a price, discount, or SLA. Escalate instead.</p>
            </div>
          )}

          {answer.missing?.length > 0 && (
            <div>
              <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">Not covered</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-neutral-700">
                {answer.missing.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          )}

          {answer.recommended_action && (
            <p className="text-sm text-neutral-700">
              <span className="font-medium">Next step:</span> {answer.recommended_action}
            </p>
          )}

          <div>
            <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">Citations</p>
            {answer.citations.length === 0 ? (
              <p className="mt-1 text-sm text-neutral-500">No citations for this answer.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {answer.citations.map((c) => (
                  <li
                    key={`${c.doc_id}-${c.snippet.slice(0, 24)}`}
                    className="rounded border border-neutral-100 p-3 text-sm"
                  >
                    <p className="font-medium text-navy-700">
                      {c.doc_id} · {c.title}
                    </p>
                    {c.section && !c.section.toLowerCase().includes('illustrative') ? (
                      <p className="text-xs text-neutral-400">{c.section}</p>
                    ) : null}
                    <p className="mt-1 text-neutral-700">“{c.snippet}”</p>
                    {c.source_url && (
                      <a
                        href={c.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-1 inline-block text-xs text-navy-600 hover:underline"
                      >
                        Open source page
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <p className="text-xs text-neutral-500">{answer.notice}</p>

          <div className="flex flex-wrap items-center gap-2 border-t border-neutral-100 pt-3">
            {answer.state === 'draft' ? (
              <>
                <button
                  type="button"
                  disabled={approve.isPending}
                  onClick={() => approve.mutate()}
                  className="cursor-pointer rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  type="button"
                  disabled={reject.isPending}
                  onClick={() => reject.mutate()}
                  className="cursor-pointer rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-700"
                >
                  Reject
                </button>
                <p className="text-xs text-neutral-500">
                  Approve = ready for you to use. Reject = discard this draft. Neither sends email.
                </p>
              </>
            ) : (
              <p className="text-xs text-neutral-600">
                This draft is <span className="font-medium">{answer.state}</span>. Ask again to create a
                new draft if you need a different answer.
              </p>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
