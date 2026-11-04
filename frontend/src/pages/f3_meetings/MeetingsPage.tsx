import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Mic, Sparkles, Trash2, UserRoundX } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { apiRequest } from '../../api/client'
import { FictionalBadge } from '../../components/FictionalBadge'
import {
  anonymizeSpeakersInTranscript,
  clearKnownSpeakers,
  extractSpeakerNamesFromTranscript,
  loadKnownSpeakers,
  saveKnownSpeakers,
} from '../../features/f3_meetings/speakerMemory'

type ExtractionItem = { value: string; status: string; quote?: string }
type Extraction = Record<string, ExtractionItem | ExtractionItem[] | undefined>

function StatusPill({ status }: { status: string }) {
  const s =
    status === 'confirmed'
      ? 'border-green-600/40 text-green-700 bg-green-50'
      : status === 'unconfirmed'
        ? 'border-amber-600/40 text-amber-700 bg-amber-50'
        : 'border-neutral-300 text-neutral-600 bg-neutral-50'
  return (
    <span className={`inline-flex rounded-md border px-2 py-0.5 text-[11px] font-medium capitalize ${s}`}>
      {status}
    </span>
  )
}

function asItems(value: ExtractionItem | ExtractionItem[] | undefined): ExtractionItem[] {
  if (!value) return []
  return Array.isArray(value) ? value : [value]
}

type MeetingsPayload = {
  account_id: string
  account_name: string
  opportunity_id: string | null
  opportunity_name: string | null
  pregenerated: {
    meeting_date: string | null
    meeting_type: string | null
    meeting_summary: string | null
    meeting_transcript: string | null
  }
  uploaded_meetings: Array<{
    meeting_id: string
    uploaded_file_name?: string
    upload_date?: string
    meeting_summary?: string
    budget_discussion?: string
  }>
  as_of_date: string
}

type UploadResult = {
  meeting_id: string
  storage_path: string
  uploaded_file_name: string
  uploaded_file_type: string
  content_hash: string
  transcript: string
  selected_match: {
    account_id: string
    account_name: string
    opportunity_id: string | null
  } | null
  suggested_matches: Array<{
    account_id: string
    account_name: string
    opportunity_id: string | null
    confidence: string
    reason: string
  }>
  needs_confirmation: boolean
}

type ExtractResult = {
  extraction: Extraction
  source: string
  ai_unavailable?: boolean
}

type SavePreview = {
  summary: string
  will_not_change: string[]
  proposed_uploaded_meeting: { meeting_id: string }
}

type TranscribeResult = {
  transcript: string
  source: string
  notice?: string
}

type FormatSpeakersResult = {
  formatted: string
  speakers: string[]
  source: string
}

export function MeetingsPage() {
  const { accountId: routeAccountId } = useParams()
  const accountId = routeAccountId || 'ACC-0181'
  const qc = useQueryClient()
  const audioInputRef = useRef<HTMLInputElement>(null)

  const [transcript, setTranscript] = useState('')
  const [uploadMeta, setUploadMeta] = useState<UploadResult | null>(null)
  const [extraction, setExtraction] = useState<Extraction | null>(null)
  const [extractSource, setExtractSource] = useState<string | null>(null)
  const [preview, setPreview] = useState<SavePreview | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [matchConfirmed, setMatchConfirmed] = useState(false)
  const [knownSpeakers, setKnownSpeakers] = useState<string[]>(() => loadKnownSpeakers())
  const [machineTranscribed, setMachineTranscribed] = useState(false)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['meetings', accountId],
    queryFn: () => apiRequest<MeetingsPayload>(`/api/v1/accounts/${accountId}/meetings`),
    enabled: !!accountId,
  })

  const resolvedAccount = uploadMeta?.selected_match?.account_id || accountId
  const opportunityId =
    uploadMeta?.selected_match?.opportunity_id || data?.opportunity_id || 'OPP-0181'

  const clearAll = () => {
    setTranscript('')
    setUploadMeta(null)
    setExtraction(null)
    setExtractSource(null)
    setPreview(null)
    setMatchConfirmed(false)
    setMachineTranscribed(false)
    setToast(null)
    if (audioInputRef.current) audioInputRef.current.value = ''
  }

  const handleClearNames = () => {
    clearKnownSpeakers()
    setKnownSpeakers([])
    if (transcript.trim()) {
      setTranscript(anonymizeSpeakersInTranscript(transcript))
    }
    setToast('Speaker names cleared to Person 1, Person 2, …')
  }

  const rememberSpeakers = (names: string[]) => {
    const merged = saveKnownSpeakers(names)
    setKnownSpeakers(merged)
  }

  const applySpeakerFormat = async (rawText: string) => {
    const result = await apiRequest<FormatSpeakersResult>('/api/v1/meetings/format-speakers', {
      method: 'POST',
      body: JSON.stringify({
        transcript: rawText,
        known_speakers: knownSpeakers,
      }),
    })
    setTranscript(result.formatted)
    setExtraction(null)
    setExtractSource(null)
    const detected =
      result.speakers.length > 0
        ? result.speakers
        : extractSpeakerNamesFromTranscript(result.formatted)
    rememberSpeakers(detected)
    return result
  }

  const loadSample = useMutation({
    mutationFn: () =>
      apiRequest<{ transcript: string; filename: string; account_id: string }>(
        '/api/v1/meetings/sample/ACC-0181',
      ),
    onSuccess: (d) => {
      setTranscript(d.transcript)
      setMachineTranscribed(false)
      setExtraction(null)
      setUploadMeta({
        meeting_id: `mtg-sample-${Date.now().toString(36)}`,
        storage_path: `meetings/sample/${d.filename}`,
        uploaded_file_name: d.filename,
        uploaded_file_type: 'txt',
        content_hash: 'sample',
        transcript: d.transcript,
        selected_match: {
          account_id: 'ACC-0181',
          account_name: 'Georgia Institute of Technology',
          opportunity_id: 'OPP-0181',
        },
        suggested_matches: [],
        needs_confirmation: false,
      })
      setMatchConfirmed(true)
      setToast('Loaded ACC-0181 demo transcript (not saved yet).')
    },
  })

  const extractIntelligence = useMutation({
    mutationFn: () =>
      apiRequest<ExtractResult>('/api/v1/meetings/extract', {
        method: 'POST',
        body: JSON.stringify({
          transcript,
          account_id: resolvedAccount,
          opportunity_id: opportunityId,
        }),
      }),
    onSuccess: (d) => {
      setExtraction(d.extraction)
      setExtractSource(d.source)
      setToast(
        d.source === 'azure_openai'
          ? 'Extraction from Azure OpenAI (review before save).'
          : 'Heuristic extraction (AI unavailable or fallback). Review before save.',
      )
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Extraction failed'),
  })

  const transcribeAudio = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      const transcribed = await apiRequest<TranscribeResult>('/api/v1/meetings/transcribe', {
        method: 'POST',
        body: form,
      })
      if (!transcribed.transcript.trim()) {
        throw new Error('No speech detected in the audio file.')
      }
      const combined = transcript.trim()
        ? `${transcript.trim()}\n\n${transcribed.transcript}`
        : transcribed.transcript
      let formatted = combined
      try {
        const result = await applySpeakerFormat(combined)
        formatted = result.formatted
      } catch {
        // Keep raw transcript if formatting fails; user can retry Format speakers.
      }
      return { transcribed, file, combined, formatted }
    },
    onSuccess: ({ transcribed, file, formatted }) => {
      setTranscript(formatted)
      setMachineTranscribed(true)
      setExtraction(null)
      const meetingId = `mtg-audio-${Date.now().toString(36)}`
      const stem = file.name.replace(/\.[^.]+$/, '') || 'audio'
      setUploadMeta({
        meeting_id: meetingId,
        storage_path: `meetings/audio-transcript/${meetingId}.txt`,
        uploaded_file_name: file.name,
        uploaded_file_type: 'audio',
        content_hash: `audio-${meetingId}`,
        transcript: formatted,
        selected_match: {
          account_id: accountId,
          account_name: data?.account_name || accountId,
          opportunity_id: data?.opportunity_id || opportunityId,
        },
        suggested_matches: [],
        needs_confirmation: false,
      })
      setMatchConfirmed(true)
      setToast(
        transcribed.notice ||
          `Transcribed ${stem} and formatted speakers. Review before save. Audio was not stored.`,
      )
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Audio transcription failed'),
  })

  const saveBody = useMemo(() => {
    if (!uploadMeta || !extraction) return null
    return {
      confirm: false,
      account_id: resolvedAccount,
      opportunity_id: opportunityId,
      storage_path: uploadMeta.storage_path,
      uploaded_file_name: uploadMeta.uploaded_file_name,
      uploaded_file_type: uploadMeta.uploaded_file_type,
      transcript,
      extraction,
      meeting_id: uploadMeta.meeting_id,
      content_hash: uploadMeta.content_hash,
    }
  }, [uploadMeta, extraction, resolvedAccount, opportunityId, transcript])

  const loadPreview = useMutation({
    mutationFn: async () => {
      if (!uploadMeta) throw new Error('Upload or transcribe audio first.')
      if (!transcript.trim()) throw new Error('Transcript is empty.')
      if (!matchConfirmed) throw new Error('Confirm the account match first.')

      let nextExtraction = extraction
      if (!nextExtraction) {
        const extracted = await apiRequest<ExtractResult>('/api/v1/meetings/extract', {
          method: 'POST',
          body: JSON.stringify({
            transcript,
            account_id: resolvedAccount,
            opportunity_id: opportunityId,
          }),
        })
        nextExtraction = extracted.extraction
        setExtraction(nextExtraction)
      }

      const body = {
        confirm: false,
        account_id: resolvedAccount,
        opportunity_id: opportunityId,
        storage_path: uploadMeta.storage_path,
        uploaded_file_name: uploadMeta.uploaded_file_name,
        uploaded_file_type: uploadMeta.uploaded_file_type,
        transcript,
        extraction: nextExtraction,
        meeting_id: uploadMeta.meeting_id,
        content_hash: uploadMeta.content_hash,
      }
      return apiRequest<SavePreview>('/api/v1/meetings/save/preview', {
        method: 'POST',
        body: JSON.stringify(body),
      })
    },
    onSuccess: setPreview,
    onError: (e) => setToast(e instanceof Error ? e.message : 'Preview failed'),
  })

  const confirmSave = useMutation({
    mutationFn: () => {
      if (!saveBody && !uploadMeta) throw new Error('Nothing to save.')
      const body = saveBody ?? {
        confirm: true,
        account_id: resolvedAccount,
        opportunity_id: opportunityId,
        storage_path: uploadMeta!.storage_path,
        uploaded_file_name: uploadMeta!.uploaded_file_name,
        uploaded_file_type: uploadMeta!.uploaded_file_type,
        transcript,
        extraction: extraction ?? {},
        meeting_id: uploadMeta!.meeting_id,
        content_hash: uploadMeta!.content_hash,
      }
      return apiRequest('/api/v1/meetings/save', {
        method: 'POST',
        body: JSON.stringify({ ...body, confirm: true }),
      })
    },
    onSuccess: () => {
      setPreview(null)
      setToast('Meeting appended to uploaded_meetings. Pre-generated meeting kept.')
      void refetch()
      void qc.invalidateQueries({ queryKey: ['meetings', accountId] })
    },
  })

  const busy =
    transcribeAudio.isPending ||
    extractIntelligence.isPending ||
    loadPreview.isPending ||
    confirmSave.isPending

  const groups: Array<{ key: string; label: string }> = [
    { key: 'meeting_summary', label: 'Summary' },
    { key: 'customer_requirements', label: 'Requirements' },
    { key: 'budget_discussion', label: 'Budget' },
    { key: 'pain_points', label: 'Pain points' },
    { key: 'objections', label: 'Objections' },
    { key: 'stakeholders', label: 'Stakeholders' },
    { key: 'competitor_mentions', label: 'Competitors' },
    { key: 'decision_criteria', label: 'Decision criteria' },
    { key: 'customer_commitments', label: 'Customer commitments' },
    { key: 'action_items', label: 'Action items' },
    { key: 'deadlines', label: 'Deadlines' },
    { key: 'recommended_next_steps', label: 'Next steps' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/risk" className="text-sm text-navy-600 hover:underline">
            ← Back
          </Link>
          <h2 className="mt-2 text-2xl font-semibold text-neutral-900">Meeting intelligence</h2>
          <p className="mt-1 text-sm text-neutral-500">
            {data?.account_name || accountId} · upload audio or paste, then save only after you confirm
          </p>
        </div>
        <FictionalBadge />
      </div>

      {toast && (
        <div className="rounded-md border border-green-600/30 bg-green-50 px-4 py-2 text-sm text-green-700">
          {toast}
        </div>
      )}

      {isLoading && <p className="text-neutral-500">Loading meetings…</p>}
      {error && (
        <p className="text-red-600">{error instanceof Error ? error.message : 'Failed to load'}</p>
      )}

      {data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-lg border border-neutral-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-neutral-900">Pre-generated meeting</h3>
            <p className="mt-1 text-xs text-neutral-500">
              {data.pregenerated.meeting_type || 'Meeting'} · {data.pregenerated.meeting_date || '—'}
            </p>
            <p className="mt-3 text-sm text-neutral-700">
              {data.pregenerated.meeting_summary || 'No pre-generated summary.'}
            </p>
            <details className="mt-3">
              <summary className="cursor-pointer text-sm text-navy-600">Show transcript</summary>
              <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-neutral-50 p-3 text-xs text-neutral-600">
                {data.pregenerated.meeting_transcript || '—'}
              </pre>
            </details>
          </section>

          <section className="rounded-lg border border-neutral-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-neutral-900">Uploaded meetings</h3>
            {data.uploaded_meetings.length === 0 ? (
              <p className="mt-2 text-sm text-neutral-500">None yet — upload audio and confirm below.</p>
            ) : (
              <ul className="mt-3 space-y-2">
                {data.uploaded_meetings.map((m) => (
                  <li key={m.meeting_id} className="rounded border border-neutral-100 p-3 text-sm">
                    <p className="font-medium text-neutral-800">
                      {m.uploaded_file_name || m.meeting_id}
                    </p>
                    <p className="text-xs text-neutral-500">{m.upload_date}</p>
                    <p className="mt-1 text-neutral-600">{m.meeting_summary || m.budget_discussion}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      <section className="rounded-lg border border-neutral-200 bg-white p-4 space-y-4">
        <h3 className="text-sm font-semibold text-neutral-900">Upload / paste transcript</h3>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => audioInputRef.current?.click()}
            className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-700 hover:bg-navy-50 disabled:opacity-50"
          >
            <Mic className="size-4" />
            {transcribeAudio.isPending ? 'Transcribing…' : 'Choose audio'}
          </button>
          <input
            ref={audioInputRef}
            type="file"
            accept="audio/*,.mp3,.wav,.m4a,.webm,.ogg,.mp4,.mpeg"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              e.target.value = ''
              if (f) transcribeAudio.mutate(f)
            }}
          />
          <button
            type="button"
            onClick={() => loadSample.mutate()}
            disabled={busy}
            className="rounded-md border border-navy-600 bg-navy-50 px-3 py-2 text-sm font-medium text-navy-700 disabled:opacity-50"
          >
            Load ACC-0181 sample TXT
          </button>
          <button
            type="button"
            onClick={clearAll}
            disabled={busy || (!transcript && !uploadMeta)}
            className="inline-flex items-center gap-2 rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
          >
            <Trash2 className="size-4" />
            Clear
          </button>
          <button
            type="button"
            onClick={handleClearNames}
            disabled={busy || (!transcript.trim() && knownSpeakers.length === 0)}
            title="Reset named speakers to Person 1, Person 2, …"
            className="inline-flex items-center gap-2 rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
          >
            <UserRoundX className="size-4" />
            Clear names
          </button>
        </div>
        <p className="text-xs text-neutral-500">
          Audio is transcribed with Groq Whisper and is not stored. Demo path: Georgia Tech
          follow-up call sample.
          {knownSpeakers.length > 0 ? ` · Remembered names: ${knownSpeakers.join(', ')}` : ''}
        </p>
        {machineTranscribed && (
          <p className="text-xs text-amber-800">
            Machine-transcribed text — review before saving. May contain STT errors.
          </p>
        )}
        <textarea
          value={transcript}
          onChange={(e) => {
            setTranscript(e.target.value)
            setExtraction(null)
            setExtractSource(null)
          }}
          rows={12}
          className="w-full rounded-md border border-neutral-300 p-3 font-mono text-xs text-neutral-800"
          placeholder="Transcript text…"
        />
        <p className="text-xs text-neutral-500">{transcript.length.toLocaleString()} characters</p>

        {uploadMeta && (
          <div className="rounded-md border border-neutral-200 bg-neutral-50 p-3 text-sm">
            <p className="font-medium text-neutral-800">Account match</p>
            <p className="mt-1 text-neutral-700">
              {uploadMeta.selected_match
                ? `${uploadMeta.selected_match.account_name} (${uploadMeta.selected_match.account_id})`
                : 'No automatic match — use ACC-0181 sample or pick a suggested match.'}
            </p>
            {uploadMeta.suggested_matches.length > 1 && (
              <ul className="mt-2 space-y-1">
                {uploadMeta.suggested_matches.map((m) => (
                  <li key={m.account_id}>
                    <button
                      type="button"
                      className="text-navy-600 hover:underline"
                      onClick={() => {
                        setUploadMeta({
                          ...uploadMeta,
                          selected_match: {
                            account_id: m.account_id,
                            account_name: m.account_name,
                            opportunity_id: m.opportunity_id,
                          },
                        })
                        setMatchConfirmed(true)
                      }}
                    >
                      {m.account_name} · {m.confidence} · {m.reason}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {!matchConfirmed && uploadMeta.selected_match && (
              <button
                type="button"
                className="mt-2 rounded-md bg-navy-600 px-3 py-1.5 text-xs font-medium text-white"
                onClick={() => setMatchConfirmed(true)}
              >
                Confirm match
              </button>
            )}
            {matchConfirmed && (
              <p className="mt-2 text-xs text-green-700">Match confirmed for save.</p>
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!transcript.trim() || !matchConfirmed || busy}
            onClick={() => extractIntelligence.mutate()}
            className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            <Sparkles className="size-4" />
            {extractIntelligence.isPending ? 'Extracting…' : 'Extract intelligence'}
          </button>
          <button
            type="button"
            disabled={!transcript || !matchConfirmed || !uploadMeta || !extraction || busy}
            onClick={() => loadPreview.mutate()}
            className="rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {loadPreview.isPending ? 'Preparing…' : 'Save to CRM (preview)'}
          </button>
        </div>
      </section>

      {extraction && (
        <section className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-4">
          <h3 className="text-sm font-semibold text-neutral-900">
            Extracted intelligence{' '}
            <span className="font-normal text-neutral-500">· {extractSource || 'rules'}</span>
          </h3>
          <p className="mt-1 text-xs text-amber-800">
            Held-back check: no invented approved budget amount or discount %.
          </p>
          <div className="mt-4 space-y-4">
            {groups.map(({ key, label }) => {
              const items = asItems(extraction[key])
              if (!items.length) return null
              return (
                <div key={key}>
                  <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
                    {label}
                  </p>
                  <ul className="mt-2 space-y-2">
                    {items.map((item, i) => (
                      <li
                        key={`${key}-${i}`}
                        className="rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <p className="text-neutral-800">{item.value}</p>
                          <StatusPill status={item.status || 'unknown'} />
                        </div>
                        {item.quote ? (
                          <p className="mt-1 text-xs italic text-neutral-500">“{item.quote}”</p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/50 p-4">
          <div className="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl">
            <h3 className="text-lg font-semibold text-neutral-900">Confirm save to CRM</h3>
            <p className="mt-2 text-sm text-neutral-600">{preview.summary}</p>
            <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-neutral-600">
              {preview.will_not_change.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setPreview(null)}
                className="rounded-md border border-neutral-300 px-3 py-2 text-sm"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => confirmSave.mutate()}
                disabled={confirmSave.isPending}
                className="rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
              >
                {confirmSave.isPending ? 'Saving…' : 'Confirm append'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
