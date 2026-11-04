const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY ?? ''
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export const env = {
  clerkPublishableKey,
  apiBaseUrl,
}

export const missingEnvVars = [
  !clerkPublishableKey ? 'VITE_CLERK_PUBLISHABLE_KEY' : null,
  !apiBaseUrl ? 'VITE_API_BASE_URL' : null,
].filter(Boolean) as string[]
