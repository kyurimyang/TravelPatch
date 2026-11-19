import { useLayoutEffect } from 'react'
import { Navigate, Outlet, useLocation, useNavigationType } from 'react-router'
import { OfflineBanner } from '../components/OfflineBanner'
import { useAuth } from '../store/auth'
import './AppFrame.css'

// Layout route: renders the shared phone-width frame, and <Outlet /> is where the
// matched child route (a page) is drawn.
export default function AppFrame() {
  const { needsConsent } = useAuth()
  const path = useLocation().pathname
  const navType = useNavigationType()
  // A6: a new screen opens at the top (the window scrolls, not the frame). Back/forward (POP) is
  // left to the browser, which restores where the user was. <ScrollRestoration> needs a data
  // router; this app uses <BrowserRouter>. Layout effect: no flash of the old position.
  useLayoutEffect(() => {
    if (navType !== 'POP') window.scrollTo(0, 0)
  }, [path, navType])
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
