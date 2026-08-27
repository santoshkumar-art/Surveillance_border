import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import { Spinner } from './components/ui'
import Alerts from './pages/Alerts'
import Analytics from './pages/Analytics'
import Dashboard from './pages/Dashboard'
import Detections from './pages/Detections'
import Login from './pages/Login'
import SettingsPage from './pages/Settings'
import SystemStatusPage from './pages/SystemStatus'
import Upload from './pages/Upload'
import VideoDetail from './pages/VideoDetail'
import Videos from './pages/Videos'
import { useAuth } from './state/AuthContext'

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner label="Restoring session…" />
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const { user, loading } = useAuth()

  return (
    <Routes>
      <Route
        path="/login"
        element={loading ? <Spinner /> : user ? <Navigate to="/" replace /> : <Login />}
      />
      <Route
        element={
          <Protected>
            <AppShell />
          </Protected>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/videos" element={<Videos />} />
        <Route path="/videos/:videoId" element={<VideoDetail />} />
        <Route path="/detections" element={<Detections />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/system" element={<SystemStatusPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
