import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'
import { loginPath } from '../lib/nav'
import { useAuth } from '../store/auth'
import './Account.css'
import './Settings.css'

const VERSION = '0.1.0'

// Settings, as far as it works without the account database (decision 2026-11-18: C on hold):
// nickname and password live in Supabase Auth itself. Mockup items that are out of the MVP
// (Naver, alerts, location) are left out.
export default function Settings() {
  const navigate = useNavigate()
  const auth = useAuth()
  const [nickname, setNickname] = useState(auth.nickname ?? '')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState<{ kind: 'error' | 'info'; text: string } | null>(null)

  if (auth.ready && !auth.user) return <Navigate to={loginPath('/settings')} replace />
  const google = auth.user?.app_metadata?.providers?.includes('google') ?? false

  async function saveNickname() {
    const error = await auth.updateProfile({ nickname: nickname.trim() })
    setMessage(error ? { kind: 'error', text: error } : { kind: 'info', text: '닉네임을 바꿨어요.' })
  }

  async function savePassword() {
    if (password.length < 8 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      setMessage({ kind: 'error', text: '비밀번호는 8자 이상, 영문과 숫자를 섞어 주세요.' })
      return
    }
    const error = await auth.updatePassword(password)
    setPassword('')
    setMessage(error ? { kind: 'error', text: error } : { kind: 'info', text: '비밀번호를 바꿨어요.' })
  }

  return (
    <div className="account settings">
      <h1>설정</h1>

      <section className="settings__group tp-fabric" aria-label="내 정보">
        <h2>내 정보</h2>
        <p className="settings__email">{auth.user?.email}</p>
        <label className="settings__row">
          <span>닉네임</span>
          <input maxLength={20} value={nickname} onChange={(e) => setNickname(e.target.value)} />
          <button type="button" disabled={!nickname.trim() || nickname.trim() === auth.nickname} onClick={saveNickname}>
            수정
          </button>
        </label>
      </section>

      <section className="settings__group tp-fabric" aria-label="로그인 연결">
        <h2>로그인 연결</h2>
        <div className="settings__row">
          <span>Google</span>
          <b className={google ? 'settings__on' : 'settings__off'}>{google ? '연결됨' : '연결 안 됨'}</b>
        </div>
        <label className="settings__row">
          <span>새 비밀번호</span>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button type="button" disabled={!password} onClick={savePassword}>
            바꾸기
          </button>
        </label>
      </section>

      {message && (
        <p className={`account__msg account__msg--${message.kind}`} role={message.kind === 'error' ? 'alert' : 'status'}>
          {message.text}
        </p>
      )}

      <section className="settings__group tp-fabric" aria-label="도움말">
        <h2>도움말</h2>
        <Link className="settings__link" to="/guide">
          이용법 보기
        </Link>
      </section>

      <section className="settings__group tp-fabric" aria-label="약관과 정책">
        <h2>약관과 정책</h2>
        <Link className="settings__link" to="/legal/terms">
          이용약관
        </Link>
        <Link className="settings__link" to="/legal/privacy">
          개인정보 처리방침
        </Link>
      </section>

      <div className="settings__bottom">
        <button
          type="button"
          className="tp-btn-quiet"
          onClick={async () => {
            await auth.signOut()
            navigate('/', { replace: true })
          }}
        >
          로그아웃
        </button>
        <Link className="settings__withdraw" to="/settings/withdraw">
          회원 탈퇴
        </Link>
        <span className="settings__version">버전 {VERSION}</span>
      </div>
    </div>
  )
}
