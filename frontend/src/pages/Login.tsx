import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { StateCard } from '../components/StateCard'
import { useAuth } from '../store/auth'
import './Account.css'

export default function Login() {
  const navigate = useNavigate()
  const auth = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ kind: 'error' | 'info'; text: string } | null>(null)

  if (!auth.available) {
    return (
      <StateCard kind="empty" title="지금은 로그인을 쓸 수 없어요">
        <p>계정 서버가 설정되지 않았어요. 로그인 없이도 이 기기에 여행을 저장해 쓸 수 있어요.</p>
      </StateCard>
    )
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMessage(null)
    const error = await auth.signIn(email.trim(), password)
    setBusy(false)
    if (error) setMessage({ kind: 'error', text: error })
    else navigate('/')
  }

  async function google() {
    const error = await auth.signInWithGoogle()
    if (error) setMessage({ kind: 'error', text: error })
  }

  async function reset() {
    if (!email.trim()) {
      setMessage({ kind: 'error', text: '비밀번호를 바꿀 이메일을 먼저 적어 주세요.' })
      return
    }
    const error = await auth.sendPasswordReset(email.trim())
    setMessage(error ? { kind: 'error', text: error } : { kind: 'info', text: '비밀번호를 바꾸는 메일을 보냈어요.' })
  }

  return (
    <div className="account">
      <h1>
        다시 만나서
        <br />
        반가워요
      </h1>

      <button type="button" className="account__social" onClick={google}>
        <span aria-hidden="true">G</span> Google로 시작하기
      </button>

      <div className="account__or">또는 이메일로</div>

      <form className="account__form" onSubmit={submit}>
        <label>
          이메일
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          비밀번호
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button type="button" className="account__link" onClick={reset}>
          비밀번호를 잊으셨나요?
        </button>
        {message && (
          <p className={`account__msg account__msg--${message.kind}`} role={message.kind === 'error' ? 'alert' : 'status'}>
            {message.text}
          </p>
        )}
        <button type="submit" className="tp-btn-primary tp-denim" disabled={busy}>
          {busy ? '확인하고 있어요…' : '로그인'}
        </button>
      </form>

      <p className="account__switch">
        처음이신가요? <Link to="/signup">회원가입</Link>
      </p>
      <p className="account__switch">
        <Link to="/">로그인 없이 둘러보기</Link>
      </p>
    </div>
  )
}
