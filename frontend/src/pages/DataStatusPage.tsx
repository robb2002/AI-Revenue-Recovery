import { useQuery } from '@tanstack/react-query'
import { apiRequest } from '../api/client'

type DataStatus = {
  schema: string
  table: string
  crm_rows: number
  as_of_date: string
  data_label: string
  kb_path: string
  sample_meetings_path: string
}

export function DataStatusPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['data-status'],
    queryFn: () => apiRequest<DataStatus>('/api/v1/data/status'),
  })

  if (isLoading) return <p className="text-neutral-500">Loading…</p>
  if (error || !data) {
    return <p className="text-red-600">{error instanceof Error ? error.message : 'Failed'}</p>
  }

  return (
    <div className="max-w-lg space-y-4 rounded-lg border border-neutral-200 bg-white p-6">
      <h2 className="text-xl font-semibold">Data status</h2>
      <dl className="space-y-2 text-sm">
        <div className="flex justify-between gap-4"><dt className="text-neutral-500">Schema</dt><dd>{data.schema}</dd></div>
        <div className="flex justify-between gap-4"><dt className="text-neutral-500">Table</dt><dd>{data.table}</dd></div>
        <div className="flex justify-between gap-4"><dt className="text-neutral-500">Rows</dt><dd>{data.crm_rows}</dd></div>
        <div className="flex justify-between gap-4"><dt className="text-neutral-500">As of</dt><dd>{data.as_of_date}</dd></div>
        <div className="flex justify-between gap-4"><dt className="text-neutral-500">Label</dt><dd>{data.data_label}</dd></div>
        <div className="flex justify-between gap-4"><dt className="text-neutral-500">KB</dt><dd className="text-right">{data.kb_path}</dd></div>
      </dl>
    </div>
  )
}
