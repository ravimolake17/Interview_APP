import { AdminPage } from './pages/AdminPage'
import { CandidatePage } from './pages/CandidatePage'

export default function App() {
  const path = window.location.pathname.toLowerCase()
  if (path.startsWith('/monitor')) {
    // HR app (intapp) opens this on Proctor in a new tab and may pass the JWT once.
    const params = new URLSearchParams(window.location.search)
    const handedOff = params.get('hr_token')
    if (handedOff) {
      localStorage.setItem('hr_access_token', handedOff)
      params.delete('hr_token')
      const clean = `${window.location.pathname}${params.toString() ? `?${params}` : ''}${window.location.hash}`
      window.history.replaceState({}, '', clean)
    }
    const hrToken = localStorage.getItem('hr_access_token')
    if (!hrToken) {
      // Proctor has no HR login page — send them back to the App host login.
      const appLogin = `${window.location.protocol}//${window.location.hostname.replace(/^proctor\./, 'intapp.')}/login`
      window.location.href = appLogin
      return null
    }
    return <AdminPage />
  }
  return <CandidatePage />
}
