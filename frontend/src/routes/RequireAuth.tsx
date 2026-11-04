import { useAuth } from '@clerk/react'
import { Navigate, Outlet, useLocation } from 'react-router'

export function RequireAuth() {
  const { isLoaded, isSignedIn } = useAuth()
  const location = useLocation()

  if (!isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-50 text-neutral-500">
        Loading session…
      </div>
    )
  }
  if (!isSignedIn) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}
