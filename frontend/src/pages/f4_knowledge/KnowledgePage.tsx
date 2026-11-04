import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Upload } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { apiRequest } from '../../api/client'
import { FictionalBadge } from '../../components/FictionalBadge'

type Doc = {
  doc_id: string
  title: string
  version: string | null
  classification: string | null
  blocker_categories: string[]
  source_kind?: string
  has_embedding?: boolean
}

type DocList = {
  items: Doc[]
  total: number
  expected_bundled: number
  docs_with_embeddings?: number
  embedding_model?: string
  embedding_dimensions?: number
  similarity_gate?: number
}

type IndexResult = {
  indexed_docs: number
  indexed_chunks: number
  embedded_chunks?: number
  retrieval_mode?: string
  embedding_model?: string
}

type UploadResult = {
  doc_id: string
  chunk_count: number
  embedded_chunks?: number
  retrieval_mode?: string
  notice?: string
}

export function KnowledgePage() {
  const qc = useQueryClient()
  const [toast, setToast] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['knowledge'],
    queryFn: () => apiRequest<DocList>('/api/v1/knowledge/documents'),
  })

  const reindex = useMutation({
    mutationFn: () => apiRequest<IndexResult>('/api/v1/knowledge/index', { method: 'POST' }),
    onSuccess: (d) => {
      void qc.invalidateQueries({ queryKey: ['knowledge'] })
      setToast(
        `Reindexed ${d.indexed_docs} docs / ${d.indexed_chunks} chunks` +
          (d.embedded_chunks != null
            ? ` · embedded ${d.embedded_chunks} via ${d.embedding_model || 'Azure'} (${d.retrieval_mode})`
            : ''),
      )
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Reindex failed'),
  })

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return apiRequest<UploadResult>('/api/v1/knowledge/upload', {
        method: 'POST',
        body: form,
      })
    },
    onSuccess: (d) => {
      void qc.invalidateQueries({ queryKey: ['knowledge'] })
      setToast(
        `Uploaded ${d.doc_id} (${d.chunk_count} chunks` +
          (d.embedded_chunks != null ? `, embedded ${d.embedded_chunks}` : '') +
          '). ' +
          (d.notice || ''),
      )
    },
    onError: (e) => setToast(e instanceof Error ? e.message : 'Upload failed'),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-semibold text-neutral-900">
            <BookOpen className="size-6 text-navy-600" />
            Knowledge base
          </h2>
          <p className="mt-1 text-sm text-neutral-500">
            Chunk → embed ({data?.embedding_model || 'text-embedding-ada-002'}) → pgvector retrieve ·
            gate {data?.similarity_gate ?? 0.72}
          </p>
        </div>
        <FictionalBadge />
      </div>

      {toast && (
        <div className="rounded-md border border-green-600/30 bg-green-50 px-4 py-2 text-sm text-green-700">
          {toast}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => reindex.mutate()}
          disabled={reindex.isPending}
          className="rounded-md bg-navy-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {reindex.isPending ? 'Indexing + embedding…' : 'Reindex bundled KB'}
        </button>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-700 hover:bg-navy-50">
          <Upload className="size-4" />
          Upload doc (.txt / .md)
          <input
            type="file"
            accept=".txt,.md"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) upload.mutate(f)
            }}
          />
        </label>
        <Link
          to="/accounts/ACC-0181/blockers"
          className="text-sm font-medium text-navy-600 hover:underline"
        >
          Open blockers workspace →
        </Link>
      </div>

      <p className="text-xs text-neutral-500">
        Pipeline: approved markdown → ## chunks → Azure {data?.embedding_model || 'ada-002'} (
        {data?.embedding_dimensions || 1536}-d) → store in kb_chunks → cosine retrieve ≥ gate →
        grounded answer. Uploads are salesperson_upload (illustrative), not open web search.
      </p>

      {isLoading && <p className="text-neutral-500">Loading documents…</p>}
      {error && (
        <p className="text-red-600">
          {error instanceof Error ? error.message : 'Failed to load'} — try Reindex.
        </p>
      )}

      {data && data.total === 0 && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          KB not indexed yet. Click <strong>Reindex bundled KB</strong> (embeds with the same Azure
          deployment as the parent Sales Intelligence app).
        </p>
      )}

      {data && data.items.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white">
          <div className="border-b border-neutral-100 px-4 py-2 text-xs text-neutral-500">
            {data.total} documents · {data.docs_with_embeddings ?? 0} with embeddings · expected
            bundled {data.expected_bundled}
          </div>
          <table className="min-w-full text-left text-sm">
            <thead className="bg-neutral-100 text-xs tracking-wide text-neutral-500 uppercase">
              <tr>
                <th className="px-4 py-3 font-medium">Doc ID</th>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium">Embedded</th>
                <th className="px-4 py-3 font-medium">Categories</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {data.items.map((d) => (
                <tr key={d.doc_id} className="hover:bg-navy-50/50">
                  <td className="px-4 py-3 font-mono text-xs text-navy-700">{d.doc_id}</td>
                  <td className="px-4 py-3 text-neutral-800">{d.title}</td>
                  <td className="px-4 py-3 text-xs text-neutral-600">
                    {d.source_kind || 'bundled_kb'}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {d.has_embedding ? (
                      <span className="text-green-700">yes</span>
                    ) : (
                      <span className="text-amber-700">no</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-neutral-500">
                    {(d.blocker_categories || []).join(', ') || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
