import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'
import { StateCard } from '../components/StateCard'
import { useAuth } from '../store/auth'
import { useTrip } from '../store/trip'
import './Account.css'
import './Settings.css'

const REASONS = ['당분간 여행 계획이 없어요', '패치가 기대와 달랐어요', '기타']

// Deleting the account itself needs the service key on the server (C on hold, 2026-11-18).
// Until then this clears what this device holds and signs out, and says the rest is pending.
export default function Withdraw() {
  const navigate = useNavigate()
  const auth = useAuth()
  const { trips, deleteTrip } = useTrip()
  const [reason, setReason] = useState<string | null>(null)
  const [agreed, setAgreed] = useState(false)
  const [done, setDone] = useState(false)

  if (auth.ready && !auth.user && !done) return <Navigate to="/login" replace />
  if (done) {
    return (
      <StateCard
        kind="empty"
        title="이 기기의 기록을 지웠어요"
        actions={
          <Link className="tp-btn-primary tp-denim" to="/">
            처음으로
          </Link>
        }
      >
        <p>계정 자체를 지우는 기능은 준비 중이에요. 준비되면 계정과 서버의 기록도 함께 지울 수 있어요.</p>
      </StateCard>
    )
  }

  async function withdraw() {
    for (const t of trips) deleteTrip(t.id)
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
        <p className="account__hint">법령에 따라 보관해야 하는 정보는 [작성 필요: 보관 기간] 동안 따로 보관한 뒤 지워요.</p>
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

      <p className="account__msg account__msg--info">
        지금은 계정 삭제 기능을 준비 중이라, 이 기기에 저장된 여행을 지우고 로그아웃해요.
      </p>

      <div className="withdraw__actions">
        <Link className="tp-btn-quiet" to="/settings">
          취소
        </Link>
        <button type="button" className="tp-btn-primary withdraw__go" disabled={!agreed} onClick={withdraw}>
          탈퇴하기
        </button>
      </div>
    </div>
  )
}
