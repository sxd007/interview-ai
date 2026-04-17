import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { Layout } from './components/Layout'
import { HomePage } from './pages/HomePage'
import { InterviewListPage } from './pages/InterviewListPage'
import { InterviewDetailPage } from './pages/InterviewDetailPage'
import { InterviewPlayerPage } from './pages/InterviewPlayerPage'
import { UploadPage } from './pages/UploadPage'
import { PipelinePage } from './pages/PipelinePage'
import { ReviewPage } from './pages/ReviewPage'
import { VoicePrintListPage } from './pages/VoicePrintListPage'
import { VoicePrintDetailPage } from './pages/VoicePrintDetailPage'
import { LoginPage } from './pages/LoginPage'
import { useAuthStore } from './stores/authStore'

function ProtectedRoute() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="interviews" element={<InterviewListPage />} />
          <Route path="interviews/:id" element={<InterviewDetailPage />} />
          <Route path="interviews/:id/play" element={<InterviewPlayerPage />} />
          <Route path="interviews/:id/pipeline" element={<PipelinePage />} />
          <Route path="interviews/:id/review" element={<ReviewPage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="voice-prints" element={<VoicePrintListPage />} />
          <Route path="voice-prints/:id" element={<VoicePrintDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
