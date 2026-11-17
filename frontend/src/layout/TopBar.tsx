import { Link, useNavigate } from 'react-router'
import wordmark from '../assets/wordmark.png'
import { useAuth } from '../store/auth'
import './TopBar.css'
import './TopBarAccount.css'

type Props = { variant: 'tab' | 'flow'; title?: string }

// tab  = top-level screens: wordmark only.
// flow = screens inside a flow: back button (+ optional title).
// Account button: settings when signed in, login otherwise. (The mockup's bell is out: no alerts in MVP.)
export default function TopBar({ variant, title }: Props) {
  const navigate = useNavigate()
  const { user } = useAuth()

  return (
    <header className="top-bar tp-pinked-bottom">
      {variant === 'tab' ? (
        <>
          <img className="top-bar__logo" src={wordmark} alt="TravelPatch" />
          <Link className="top-bar__account" to={user ? '/settings' : '/login'} aria-label={user ? '설정' : '로그인'}>
            <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <circle cx="12" cy="8" r="4" />
              <path d="M4 20c1.5-4 4.5-6 8-6s6.5 2 8 6" />
            </svg>
          </Link>
        </>
      ) : (
        <>
          {/* navigate(-1) = browser "back". Fine inside a flow; entering a flow URL directly has no history to go back to. */}
          <button type="button" className="top-bar__back" aria-label="뒤로가기" onClick={() => navigate(-1)}>
            <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 18l-6-6 6-6" />
            </svg>
          </button>
          {title && <h1 className="top-bar__title">{title}</h1>}
        </>
      )}
    </header>
  )
}
