import { useEffect, useLayoutEffect } from 'react'
import { Navigate, Outlet, useLocation, useNavigate, useNavigationType } from 'react-router'
import { AccountNotices } from '../components/AccountNotices'
import { OfflineBanner } from '../components/OfflineBanner'
import { takeHeldNext } from '../lib/nav'
import { useAuth } from '../store/auth'
import './AppFrame.css'

// Layout route: renders the shared phone-width frame, and <Outlet /> is where the
// matched child route (a page) is drawn.
export default function AppFrame() {
  const { needsConsent, ready, user } = useAuth()
  const navigate = useNavigate()
  const path = useLocation().pathname
  const navType = useNavigationType()
  // A6: a new screen opens at the top (the window scrolls, not the frame). Back/forward (POP) is
  // left to the browser, which restores where the user was. <ScrollRestoration> needs a data
  // router; this app uses <BrowserRouter>. Layout effect: no flash of the old position.
  useLayoutEffect(() => {
    if (navType !== 'POP') window.scrollTo(0, 0)
  }, [path, navType])
  // Back from Google sign-in (which always lands on "/"): go on to the screen the user wanted,
  // once the account is read and the terms are agreed.
  useEffect(() => {
    if (!ready || !user || needsConsent) return
    const next = takeHeldNext()
    if (next && next !== path) navigate(next, { replace: true })
  }, [ready, user, needsConsent, path, navigate])
  // Signed in without agreeing to the current terms (e.g. first Google login): finish that first.
  // The terms themselves stay readable.
  if (needsConsent && path !== '/consent' && !path.startsWith('/legal')) {
    return <Navigate to="/consent" replace />
  }
  return (
    <div className="app-frame">
      <div className="app-frame__column tp-linen-tex">
        <OfflineBanner />
        <AccountNotices />
        <Outlet />
      </div>
    </div>
  )
}
