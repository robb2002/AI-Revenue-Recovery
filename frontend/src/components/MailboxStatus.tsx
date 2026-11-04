import { useQuery } from '@tanstack/react-query'
import { Mail } from 'lucide-react'
import { apiRequest } from '../api/client'
import { env } from '../lib/env'

type GmailStatus = {
  connected: boolean
  mode: string
  mailbox_email?: string
  label?: string
  can_send?: boolean
  message?: string
  pending_crm_approvals?: number
  login_hint?: string
}

export function MailboxStatus() {
  const { data } = useQuery({
    queryKey: ['gmail-status'],
    queryFn: () => apiRequest<GmailStatus>('/api/v1/gmail/status'),
    staleTime: 30_000,
  })

  const email =
    data?.mailbox_email || data?.login_hint || env.gmailLoginHint || 'Sales mailbox'
  const connected = Boolean(data?.connected)
  const pending = data?.pending_crm_approvals ?? 0

  return (
    <span
      className={[
        'inline-flex max-w-xs items-center gap-1.5 truncate rounded-md border px-2.5 py-1 text-xs font-medium',
        connected
          ? 'border-green-600/25 bg-green-50 text-green-800'
          : 'border-neutral-200 bg-neutral-50 text-neutral-600',
      ].join(' ')}
      title={data?.message || email}
    >
      <Mail className="size-3.5 shrink-0" strokeWidth={1.75} />
      <span className="truncate">
        {connected ? 'Gmail' : 'Gmail'}
        {` · ${email}`}
        {pending > 0 ? ` · ${pending} pending` : connected ? ' · read-only' : ' · connect on Briefing'}
      </span>
    </span>
  )
}
