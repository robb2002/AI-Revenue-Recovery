import { ClerkProvider } from '@clerk/react'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { BrowserRouter, useNavigate } from 'react-router'
import { env, missingEnvVars } from './lib/env'
import { queryClient } from './lib/queryClient'
import { AppRoutes } from './routes/AppRoutes'

function ClerkProviderWithRouter({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  return (
    <ClerkProvider
      publishableKey={env.clerkPublishableKey}
      routerPush={(to) => navigate(to)}
      routerReplace={(to) => navigate(to, { replace: true })}
      signInUrl="/login"
      signUpUrl="/login"
      signInFallbackRedirectUrl="/"
      signUpFallbackRedirectUrl="/"
      afterSignOutUrl="/login"
      appearance={{
        variables: {
          colorPrimary: '#1E3A66',
          colorBackground: '#FFFFFF',
          borderRadius: '0.5rem',
        },
      }}
    >
      {children}
    </ClerkProvider>
  )
}

export function App() {
  if (missingEnvVars.length > 0) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-neutral-50 p-6">
        <p className="text-sm text-neutral-700">
          Missing env: {missingEnvVars.join(', ')}. Copy frontend/.env.example to frontend/.env.
        </p>
      </main>
    )
  }

  return (
    <BrowserRouter>
      <ClerkProviderWithRouter>
        <QueryClientProvider client={queryClient}>
          <AppRoutes />
        </QueryClientProvider>
      </ClerkProviderWithRouter>
    </BrowserRouter>
  )
}
