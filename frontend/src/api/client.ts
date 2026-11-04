import { getToken } from '@clerk/react'
import { env } from '../lib/env'

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  let token: string | null = null
  try {
    token = await getToken()
  } catch {
    /* public routes may omit token */
  }

  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body !== undefined) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${env.apiBaseUrl}${path}`, { ...init, headers })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { code?: string; message?: string }
    } | null
    throw new ApiError(
      response.status,
      body?.error?.code ?? 'INTERNAL_ERROR',
      body?.error?.message ?? 'The request failed.',
    )
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
