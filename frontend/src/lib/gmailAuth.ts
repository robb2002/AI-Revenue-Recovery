import { env } from './env'
import { loadGoogleIdentityScript } from './loadGoogleScript'

const TOKEN_STORAGE_KEY = 'rr_gmail_access_token'
const TOKEN_EXPIRY_STORAGE_KEY = 'rr_gmail_access_token_expires_at'
const SCOPES_STORAGE_KEY = 'rr_gmail_granted_scopes'
const GMAIL_READONLY_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'

type TokenClientResponse = {
  access_token?: string
  expires_in?: number
  scope?: string
  error?: string
  error_description?: string
}

declare global {
  interface Window {
    google?: {
      accounts?: {
        oauth2?: {
          initTokenClient: (config: {
            client_id: string
            scope: string
            hint?: string
            callback: (response: TokenClientResponse) => void
            error_callback?: (error: { message?: string; type?: string }) => void
          }) => { requestAccessToken: (override?: { prompt?: string }) => void }
          revoke: (token: string, done: () => void) => void
        }
      }
    }
  }
}

function hasGmailScope(scopeString: string | null | undefined): boolean {
  if (!scopeString) return false
  return scopeString.split(/\s+/).includes(GMAIL_READONLY_SCOPE)
}

function readStoredAuth(): { token: string | null; expiresAt: number } {
  const token = sessionStorage.getItem(TOKEN_STORAGE_KEY)
  const expiresAtRaw = sessionStorage.getItem(TOKEN_EXPIRY_STORAGE_KEY)
  const scopes = sessionStorage.getItem(SCOPES_STORAGE_KEY) ?? ''
  const expiresAt = expiresAtRaw ? Number(expiresAtRaw) : 0

  if (!token || !expiresAt || Date.now() >= expiresAt || !hasGmailScope(scopes)) {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY)
    sessionStorage.removeItem(TOKEN_EXPIRY_STORAGE_KEY)
    sessionStorage.removeItem(SCOPES_STORAGE_KEY)
    return { token: null, expiresAt: 0 }
  }
  return { token, expiresAt }
}

function persistToken(token: string, expiresInSeconds?: number, scopeString?: string) {
  const lifetimeMs = Math.max((expiresInSeconds ?? 3600) - 60, 60) * 1000
  const nextExpiry = Date.now() + lifetimeMs
  const scopes = scopeString ?? GMAIL_READONLY_SCOPE
  sessionStorage.setItem(TOKEN_STORAGE_KEY, token)
  sessionStorage.setItem(TOKEN_EXPIRY_STORAGE_KEY, String(nextExpiry))
  sessionStorage.setItem(SCOPES_STORAGE_KEY, scopes)
}

export function clearGmailToken() {
  const stored = sessionStorage.getItem(TOKEN_STORAGE_KEY)
  if (stored && window.google?.accounts?.oauth2) {
    window.google.accounts.oauth2.revoke(stored, () => undefined)
  }
  sessionStorage.removeItem(TOKEN_STORAGE_KEY)
  sessionStorage.removeItem(TOKEN_EXPIRY_STORAGE_KEY)
  sessionStorage.removeItem(SCOPES_STORAGE_KEY)
}

export function isGmailConfigured(): boolean {
  return Boolean(env.googleClientId)
}

export function peekGmailAccessToken(): string | null {
  return readStoredAuth().token
}

export async function connectGmail(): Promise<string> {
  if (!env.googleClientId) {
    throw new Error('Missing VITE_GOOGLE_CLIENT_ID. Add it to frontend/.env and restart Vite.')
  }
  await loadGoogleIdentityScript()
  return requestToken('consent')
}

export async function getValidGmailAccessToken(): Promise<string> {
  const stored = readStoredAuth()
  if (stored.token && Date.now() < stored.expiresAt) {
    return stored.token
  }
  return connectGmail()
}

function requestToken(prompt?: string): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!window.google?.accounts?.oauth2) {
      reject(new Error('Google Identity Services is not loaded.'))
      return
    }

    const client = window.google.accounts.oauth2.initTokenClient({
      client_id: env.googleClientId,
      // Only the scope we need for Sync Emails (avoids extra consent-screen issues).
      scope: GMAIL_READONLY_SCOPE,
      hint: env.gmailLoginHint || undefined,
      callback: (response) => {
        if (response.error || !response.access_token) {
          reject(
            new Error(
              response.error_description || response.error || 'Google Gmail connect failed.',
            ),
          )
          return
        }
        if (!hasGmailScope(response.scope)) {
          reject(
            new Error(
              'Gmail permission was not granted. Allow “View your email messages” and try again.',
            ),
          )
          return
        }
        persistToken(response.access_token, response.expires_in, response.scope)
        resolve(response.access_token)
      },
      error_callback: (error) => {
        const detail = error.message || error.type || 'Google Gmail connect failed.'
        reject(
          new Error(
            `${detail} Check Google Cloud: OAuth client type = Web application, Authorized JavaScript origins includes exactly http://localhost:5173, Gmail API enabled, and this email is a Test user.`,
          ),
        )
      },
    })

    client.requestAccessToken(prompt ? { prompt } : undefined)
  })
}
