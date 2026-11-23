import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { allAgreed, ConsentList, NO_CONSENT } from '../components/ConsentList'
import { loginPath } from '../lib/nav'
import { useAuth } from '../store/auth'
import './Account.css'

// "가입 마무리": a first Google login has an account but no agreement or nickname yet.
export default function Consent() {
  const navigate = useNavigate()
  const auth = useAuth()
  const fromGoogle = (auth.user?.user_metadata?.full_name as string | undefined) ?? ''
  const [nickname, setNickname] = useState(auth.nickname ?? fromGoogle)
  const [consent, setConsent] = useState(NO_CONSENT)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (auth.ready && !auth.user) return <Navigate to={loginPath('/consent')} replace />

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    const err = await auth.agree(nickname.trim(), { age14: true, terms: true, privacy: true })
    setBusy(false)
    if (err) setError(err)
    else navigate('/', { replace: true })
  }

  return (
    <div className="account">
      <span className="account__badge">Google로 가입 중</span>
      <h1>거의 다 됐어요</h1>
      <p className="account__lead">받은 정보를 확인하고, 약관에 동의해 주세요.</p>

      <form className="account__form" onSubmit={submit}>
        <label>
          이메일 · Google에서 받음
          <input value={auth.user?.email ?? ''} readOnly />
        </label>
        <label>
          닉네임
          <input maxLength={20} value={nickname} onChange={(e) => setNickname(e.target.value)} />
          <span className="account__hint">여행 화면에 보이는 이름이에요. 나중에 바꿀 수 있어요.</span>
        </label>
        <ConsentList value={consent} onChange={setConsent} />
        {error && (
          <p className="account__msg account__msg--error" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          className="tp-btn-primary tp-denim"
          disabled={!allAgreed(consent) || nickname.trim() === '' || busy}
        >
          동의하고 시작하기
        </button>
      </form>
    </div>
  )
}
