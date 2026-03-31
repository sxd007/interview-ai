import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { HomePage } from './pages/HomePage'
import { InterviewListPage } from './pages/InterviewListPage'
import { InterviewDetailPage } from './pages/InterviewDetailPage'
import { InterviewPlayerPage } from './pages/InterviewPlayerPage'
import { UploadPage } from './pages/UploadPage'
import { PipelinePage } from './pages/PipelinePage'
import { ReviewPage } from './pages/ReviewPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="interviews" element={<InterviewListPage />} />
        <Route path="interviews/:id" element={<InterviewDetailPage />} />
        <Route path="interviews/:id/play" element={<InterviewPlayerPage />} />
        <Route path="interviews/:id/pipeline" element={<PipelinePage />} />
        <Route path="interviews/:id/review" element={<ReviewPage />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

export default App
