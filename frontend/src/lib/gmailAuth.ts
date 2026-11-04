import { env } from './env'

const GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly openid email profile'
const TOKEN_KEY = 'lumora_gmail_access_token'
const TOKEN_EXP_KEY = 'lumora_gmail_access_token_exp'

type TokenClient = {
  requestAccessToken: (opts?: { prompt?: string }) => void
}

declare global {
  interface Window {
    google?: {
      accounts: {
        oauth2: {
          initTokenClient: (cfg: {
            client_id: string
            scope: string
            hint?: string
            callback: (resp: {
              access_token?: string
              expires_in?: number
              error?: string
            }) => void
          }) => TokenClient
        }
      }
    }
  }
}

let scriptPromise: Promise<void> | null = null
let inflight: Promise<string> | null = null

function loadGis(): Promise<void> {
  if (window.google?.accounts?.oauth2) return Promise.resolve()
  if (scriptPromise) return scriptPromise
  scriptPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = 'https://accounts.google.com/gsi/client'
    s.async = true
    s.onload = () => resolve()
    s.onerror = () => reject(new Error('Could not load Google Identity Services'))
    document.head.appendChild(s)
  })
  return scriptPromise
}

function readCachedToken(): string | null {
  try {
    const token = sessionStorage.getItem(TOKEN_KEY)
    const exp = Number(sessionStorage.getItem(TOKEN_EXP_KEY) || 0)
    // Refresh 2 minutes before expiry
    if (token && Date.now() < exp - 120_000) return token
  } catch {
    /* ignore */
  }
  return null
}

function writeCachedToken(token: string, expiresInSec?: number) {
  try {
    const ttlMs = Math.max(60, Number(expiresInSec) || 3600) * 1000
    sessionStorage.setItem(TOKEN_KEY, token)
    sessionStorage.setItem(TOKEN_EXP_KEY, String(Date.now() + ttlMs))
  } catch {
    /* ignore */
  }
}

export function clearGmailAccessToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(TOKEN_EXP_KEY)
  } catch {
    /* ignore */
  }
}

/** Reuse token after first consent; popup only when missing/expired/revoked. */
export async function requestGmailAccessToken(): Promise<string> {
  const cached = readCachedToken()
  if (cached) return cached

  if (inflight) return inflight

  if (!env.googleClientId) {
    throw new Error('VITE_GOOGLE_CLIENT_ID is not configured')
  }
  await loadGis()
  if (!window.google?.accounts?.oauth2) {
    throw new Error('Google Identity Services unavailable')
  }

  inflight = new Promise<string>((resolve, reject) => {
    const client = window.google!.accounts.oauth2.initTokenClient({
      client_id: env.googleClientId,
      scope: GMAIL_SCOPE,
      hint: env.gmailLoginHint || undefined,
      callback: (resp) => {
        if (resp.error || !resp.access_token) {
          clearGmailAccessToken()
          reject(new Error(resp.error || 'Gmail authorization failed'))
          return
        }
        writeCachedToken(resp.access_token, resp.expires_in)
        resolve(resp.access_token)
      },
    })
    // First time may show consent; later calls use cached token above.
    client.requestAccessToken({ prompt: '' })
  }).finally(() => {
    inflight = null
  })

  return inflight
}
