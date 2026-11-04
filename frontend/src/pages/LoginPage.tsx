import { SignIn, useAuth } from '@clerk/react'
import { Navigate, useLocation } from 'react-router'

export function LoginPage() {
  const { isLoaded, isSignedIn } = useAuth()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (isLoaded && isSignedIn) return <Navigate to={from} replace />

  return (
    <div className="grid min-h-screen bg-neutral-50 lg:grid-cols-2">
      <section className="hidden flex-col justify-between bg-navy-800 p-12 text-white lg:flex">
        <div>
          <p className="text-xs font-medium tracking-wide text-navy-300 uppercase">Lumora Learning</p>
          <h1 className="mt-3 text-3xl font-semibold leading-tight">
            Recover quiet deals. Prioritize risk. Hand off cleanly.
          </h1>
          <p className="mt-4 max-w-md text-navy-200">
            Evidence-backed recommendations for sales reps. Drafts stay drafts until you approve —
            nothing is sent automatically.
          </p>
        </div>
        <ul className="space-y-2 text-sm text-navy-200">
          <li>Fact · Interpretation · Recommended action</li>
          <li>Rules own the score · AI explains</li>
          <li>Fictional demo CRM · Clerk sign-in</li>
        </ul>
      </section>

      <main className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <h2 className="mb-6 text-center text-xl font-semibold text-neutral-900 lg:hidden">
            Lumora Revenue Recovery
          </h2>
          <SignIn
            routing="path"
            path="/login"
            withSignUp={false}
            fallbackRedirectUrl={from}
            signUpFallbackRedirectUrl={from}
          />
          <p className="mt-6 text-center text-xs text-neutral-500">
            One role: Sales Representative. Passwords never reach our API.
          </p>
        </div>
      </main>
    </div>
  )
}
