import { Navigate, Outlet, useLocation } from 'react-router'
import { OfflineBanner } from '../components/OfflineBanner'
import { useAuth } from '../store/auth'
import './AppFrame.css'

// Layout route: renders the shared phone-width frame, and <Outlet /> is where the
// matched child route (a page) is drawn.
export default function AppFrame() {
  const { needsConsent } = useAuth()
  const path = useLocation().pathname
  // Signed in without agreeing to the current terms (e.g. first Google login): finish that first.
  // The terms themselves stay readable.
  if (needsConsent && path !== '/consent' && !path.startsWith('/legal')) {
    return <Navigate to="/consent" replace />
  }
  return (
    <div className="app-frame">
      <div className="app-frame__column tp-linen-tex">
        <OfflineBanner />
        <Outlet />
      </div>
    </div>
  )
}
