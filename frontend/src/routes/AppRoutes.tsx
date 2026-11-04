import { Navigate, Route, Routes } from 'react-router'
import { AppShell } from '../components/AppShell'
import { BriefingPage } from '../pages/BriefingPage'
import { DataStatusPage } from '../pages/DataStatusPage'
import { LoginPage } from '../pages/LoginPage'
import { RecoveryDetailPage } from '../pages/f1_recovery/RecoveryDetailPage'
import { RecoveryListPage } from '../pages/f1_recovery/RecoveryListPage'
import { PlaceholderPage } from '../pages/PlaceholderPage'
import { RequireAuth } from './RequireAuth'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login/*" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<BriefingPage />} />
          <Route path="recovery" element={<RecoveryListPage />} />
          <Route path="recovery/:accountId" element={<RecoveryDetailPage />} />
          <Route
            path="risk"
            element={
              <PlaceholderPage
                title="Revenue risk prioritizer"
                blurb="F2 — open/stalled deals ranked by rules score with evidence."
              />
            }
          />
          <Route path="risk/:accountId" element={<PlaceholderPage title="Deal risk" blurb="F2 detail — coming next." />} />
          <Route path="knowledge" element={<PlaceholderPage title="Knowledge base" blurb="F4 document index." />} />
          <Route path="data" element={<DataStatusPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
