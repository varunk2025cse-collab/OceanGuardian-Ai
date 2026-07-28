import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { Sidebar } from './components/layout/Sidebar'
import { SystemModeBanner } from './components/layout/SystemModeBanner'
import { LoginPagePremium } from './pages/LoginPagePremium'
import { DashboardPagePremium } from './pages/DashboardPagePremium'
import { SOSAlertsPagePremium } from './pages/SOSAlertsPagePremium'
import { MapPagePremium } from './pages/MapPagePremium'
import { FishermenPagePremium } from './pages/FishermenPagePremium'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { IncidentsPage } from './pages/IncidentsPage'
import { useState } from 'react'

function ProtectedLayout() {
  const { user } = useAuth()
  const [activeSosCount, setActiveSosCount] = useState(0)
  if (!user) return <Navigate to="/login" replace />
  return (
    <div className="flex min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800">
      <Sidebar activeSosCount={activeSosCount} />
      <div className="flex-1 flex flex-col">
        <SystemModeBanner />
        <main className="flex-1 p-8 overflow-y-auto">
          <Outlet context={{ setActiveSosCount }} />
        </main>
      </div>
    </div>
  )
}

function SOSPageWrapper() {
  const [, setCount] = useState(0)
  return <SOSAlertsPagePremium onCountChange={setCount} />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPagePremium />} />
          <Route element={<ProtectedLayout />}>
            <Route path="/" element={<DashboardPagePremium />} />
            <Route path="/sos" element={<SOSPageWrapper />} />
            <Route path="/map" element={<MapPagePremium />} />
            <Route path="/fishermen" element={<FishermenPagePremium />} />
            <Route path="/incidents" element={<IncidentsPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
