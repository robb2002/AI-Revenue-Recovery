const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY ?? ''
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')
const signalScoutFeature =
  String(import.meta.env.VITE_SIGNAL_SCOUT_FEATURE ?? 'true').toLowerCase() !== 'false'
const googleClientId = (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined)?.trim() || ''
const gmailLoginHint =
  (import.meta.env.VITE_GMAIL_LOGIN_HINT as string | undefined)?.trim().toLowerCase() || ''

export const env = {
  clerkPublishableKey,
  apiBaseUrl,
  /** When false, Signal Scout nav + routes are hidden */
  signalScoutFeature,
  googleClientId,
  gmailLoginHint,
}

export const missingEnvVars = [
  !clerkPublishableKey ? 'VITE_CLERK_PUBLISHABLE_KEY' : null,
  !apiBaseUrl ? 'VITE_API_BASE_URL' : null,
].filter(Boolean) as string[]
