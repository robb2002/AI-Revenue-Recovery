import { Navigate, Route, Routes } from 'react-router'
import { AppShell } from '../components/AppShell'
import { BriefingPage } from '../pages/BriefingPage'
import { DataStatusPage } from '../pages/DataStatusPage'
import { LoginPage } from '../pages/LoginPage'
import { RecoveryDetailPage } from '../pages/f1_recovery/RecoveryDetailPage'
import { RecoveryListPage } from '../pages/f1_recovery/RecoveryListPage'
import { RiskDetailPage } from '../pages/f2_risk/RiskDetailPage'
import { RiskListPage } from '../pages/f2_risk/RiskListPage'
import { MeetingsPage } from '../pages/f3_meetings/MeetingsPage'
import { BlockersPage } from '../pages/f4_blockers/BlockersPage'
import { KnowledgePage } from '../pages/f4_knowledge/KnowledgePage'
import { DraftsPage } from '../pages/f5_drafts/DraftsPage'
import { HandoffPage } from '../pages/f6_handoff/HandoffPage'
import { SignalScoutHomePage } from '../pages/f7_signal_scout/SignalScoutHomePage'
import { SignalScoutTargetPage } from '../pages/f7_signal_scout/SignalScoutTargetPage'
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
          <Route path="risk" element={<RiskListPage />} />
          <Route path="risk/:accountId" element={<RiskDetailPage />} />
          <Route path="accounts/:accountId/meetings" element={<MeetingsPage />} />
          <Route path="meetings" element={<MeetingsPage />} />
          <Route path="accounts/:accountId/blockers" element={<BlockersPage />} />
          <Route path="blockers" element={<BlockersPage />} />
          <Route path="accounts/:accountId/drafts" element={<DraftsPage />} />
          <Route path="drafts" element={<DraftsPage />} />
          <Route path="accounts/:accountId/handoff" element={<HandoffPage />} />
          <Route path="handoff" element={<HandoffPage />} />
          <Route path="signal-scout" element={<SignalScoutHomePage />} />
          <Route path="signal-scout/:targetId" element={<SignalScoutTargetPage />} />
          <Route path="knowledge" element={<KnowledgePage />} />
          <Route path="data" element={<DataStatusPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
