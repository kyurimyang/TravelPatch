import { useState } from 'react'
import { Link, Navigate } from 'react-router'
import { allAgreed, ConsentList, NO_CONSENT } from '../components/ConsentList'
import { StateCard } from '../components/StateCard'
import { useAuth } from '../store/auth'
import './Account.css'

// 8+ characters with both letters and digits, as the mockup says. Supabase checks length again.
const strongEnough = (p: string) => p.length >= 8 && /[A-Za-z]/.test(p) && /\d/.test(p)

export default function Signup() {
  const auth = useAuth()
  const [nickname, setNickname] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [again, setAgain] = useState('')
  const [consent, setConsent] = useState(NO_CONSENT)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)

  if (!auth.available) {
    return (
      <StateCard kind="empty" title="지금은 가입할 수 없어요">
        <p>계정 서버가 설정되지 않았어요. 로그인 없이도 이 기기에 여행을 저장해 쓸 수 있어요.</p>
      </StateCard>
    )
  }
  // With "Confirm email" off (decision 2026-11-22) sign-up signs the user in at once: go home.
  // With it on, there is no session yet and the mail screen below is the right answer.
  if (auth.user) return <Navigate to="/" replace />
  if (sent) {
    return (
      <StateCard
        kind="empty"
        title="메일함을 확인해 주세요"
        actions={
          <Link className="tp-btn-primary tp-denim" to="/login">
            로그인으로
          </Link>
        }
      >
        <p>{email}로 가입 확인 메일을 보냈어요. 메일 속 버튼을 누르면 가입이 끝나요.</p>
      </StateCard>
    )
  }

  const pwOk = strongEnough(password)
  const canSubmit = nickname.trim() !== '' && email.trim() !== '' && pwOk && password === again && allAgreed(consent) && !busy

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    setBusy(true)
    setError(null)
    const err = await auth.signUp(nickname.trim(), email.trim(), password, { age14: true, terms: true, privacy: true })
    setBusy(false)
    if (err) setError(err)
    else setSent(true)
  }

  return (
    <div className="account">
      <h1>
        첫 원단을
        <br />
        재단해 볼까요?
      </h1>
      <p className="account__lead">가입하면 여행 일정과 패치를 계정에 남겨 다른 기기에서도 볼 수 있어요.</p>

      <button type="button" className="account__social" onClick={() => auth.signInWithGoogle().then((e) => e && setError(e))}>
        <span aria-hidden="true">G</span> Google로 가입하기
      </button>

      <div className="account__or">또는 이메일로 가입</div>

      <form className="account__form" onSubmit={submit}>
        <label>
          닉네임
          <input autoComplete="nickname" maxLength={20} value={nickname} onChange={(e) => setNickname(e.target.value)} />
        </label>
        <label>
          이메일
          <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          비밀번호
          <input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <span className={password && !pwOk ? 'account__hint account__hint--warn' : 'account__hint'}>
            8자 이상, 영문과 숫자를 섞어 주세요.
          </span>
        </label>
        <label>
          비밀번호 확인
          <input type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
          {again && again !== password && <span className="account__hint account__hint--warn">비밀번호가 서로 달라요.</span>}
        </label>

        <ConsentList value={consent} onChange={setConsent} />

        {error && (
          <p className="account__msg account__msg--error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="tp-btn-primary tp-denim" disabled={!canSubmit}>
          {busy ? '가입하고 있어요…' : '가입하고 시작하기'}
        </button>
      </form>

      <p className="account__switch">
        이미 계정이 있나요? <Link to="/login">로그인</Link>
      </p>
    </div>
  )
}
