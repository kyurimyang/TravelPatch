import { useNavigate } from 'react-router'
import wordmark from '../assets/wordmark.png'
import './TopBar.css'

type Props = { variant: 'tab' | 'flow'; title?: string }

// tab  = top-level screens: wordmark only.
// flow = screens inside a flow: back button (+ optional title).
// The bell / account buttons from the mockup come later (stages 4-5), once their routes exist.
export default function TopBar({ variant, title }: Props) {
  const navigate = useNavigate()

  return (
    <header className="top-bar tp-pinked-bottom">
      {variant === 'tab' ? (
        <img className="top-bar__logo" src={wordmark} alt="TravelPatch" />
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
