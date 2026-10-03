import { AdminPage } from './pages/AdminPage'
import { CandidatePage } from './pages/CandidatePage'

export default function App() {
  const path = window.location.pathname.toLowerCase()
  if (path.startsWith('/monitor')) {
    const hrToken = localStorage.getItem('hr_access_token')
    if (!hrToken) {
      window.location.href = '/login'
      return null
    }
    return <AdminPage />
  }
  return <CandidatePage />
}
