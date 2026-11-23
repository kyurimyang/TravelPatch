import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'
import { deleteRequest } from '../api/http'
import { StateCard } from '../components/StateCard'
import { loginPath } from '../lib/nav'
import { useAuth } from '../store/auth'
import './Account.css'
import './Settings.css'

const REASONS = ['당분간 여행 계획이 없어요', '패치가 기대와 달랐어요', '기타']

// DELETE /me deletes the account on the server (2026-11-23); the database cascades to every
// trip, patch and consent. Then this device signs out.
export default function Withdraw() {
  const navigate = useNavigate()
  const auth = useAuth()
  const [reason, setReason] = useState<string | null>(null)
  const [agreed, setAgreed] = useState(false)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (auth.ready && !auth.user && !done) return <Navigate to={loginPath('/settings/withdraw')} replace />
  if (done) {
    return (
      <StateCard
        kind="empty"
        title="계정을 지웠어요"
        actions={
          <Link className="tp-btn-primary tp-denim" to="/">
            처음으로
          </Link>
        }
      >
        <p>계정과 여행 일정, 패치 기록을 모두 지웠어요. 그동안 써 주셔서 고마워요.</p>
      </StateCard>
    )
  }

  async function withdraw() {
    setBusy(true)
    setError(null)
    try {
      await deleteRequest('/me')
    } catch {
      // Nothing was deleted: the account is as it was and the user can try again.
      setError('계정을 지우지 못했어요. 잠시 뒤 다시 해 주세요.')
      setBusy(false)
      return
    }
    await auth.signOut()
    setDone(true)
    navigate('/settings/withdraw', { replace: true })
  }

  return (
    <div className="account settings">
      <h1>
        탈퇴하기 전에
        <br />
        확인해 주세요
      </h1>

      <section className="settings__group tp-fabric" aria-label="지워지는 것">
        <h2>탈퇴하면 바로 지워지고 되돌릴 수 없어요</h2>
        <ul className="withdraw__list">
          <li>등록한 여행 일정과 패치 기록</li>
          <li>패치워크와 배지</li>
          <li>연결된 Google 로그인</li>
        </ul>
        <p className="account__hint">법령에 따라 따로 보관하는 정보는 없어요.</p>
      </section>

      <fieldset className="settings__group withdraw__reasons">
        <legend>떠나는 이유 (선택)</legend>
        {REASONS.map((r) => (
          <label key={r}>
            <input type="radio" name="reason" checked={reason === r} onChange={() => setReason(r)} />
            {r}
          </label>
        ))}
      </fieldset>

      <label className="withdraw__agree">
        <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />위 내용을 확인했고, 탈퇴에
        동의해요
      </label>

      {error && (
        <p className="account__msg account__msg--error" role="alert">
          {error}
        </p>
      )}

      <div className="withdraw__actions">
        <Link className="tp-btn-quiet" to="/settings">
          취소
        </Link>
        <button type="button" className="tp-btn-primary withdraw__go" disabled={!agreed || busy} onClick={withdraw}>
          {busy ? '지우고 있어요…' : '탈퇴하기'}
        </button>
      </div>
    </div>
  )
}
