import { useState } from 'react'
import { withJosa } from '../lib/josa'
import { useTrip } from '../store/trip'
import './AccountNotices.css'

// Questions the account needs answered, shown on top of whatever screen is open:
// - right after signing in, trips made on this device without an account (move them in?)
// - a trip changed or deleted on another device while this one had unsaved changes
// Without these the trips looked lost: the store held them, no screen asked about them.
export function AccountNotices() {
  const { trips, guestToMove, moveGuestTrips, conflict, resolveConflict } = useTrip()
  const [busy, setBusy] = useState(false)

  if (conflict) {
    const city = trips.find((t) => t.id === conflict.tripId)?.city
    const name = city ? `${city} 여행` : '이 여행'
    const gone = conflict.reason === 'gone'
    async function choose(choice: 'theirs' | 'mine') {
      setBusy(true)
      await resolveConflict(choice)
      setBusy(false)
    }
    return (
      <section className="account-notice tp-fabric" role="alert" aria-label="다른 기기의 변경">
        <b className="account-notice__title">
          {gone ? `다른 기기에서 ${withJosa(name, '을/를')} 지웠어요` : `다른 기기에서 ${withJosa(name, '이/가')} 바뀌었어요`}
        </b>
        <p className="account-notice__text">
          이 기기에서 고친 내용이 아직 저장되지 않았어요. 어느 쪽을 남길지 골라 주세요.
        </p>
        <div className="account-notice__actions">
          <button type="button" className="account-notice__btn account-notice__btn--main" disabled={busy} onClick={() => choose('mine')}>
            이 기기 내용 남기기
          </button>
          <button type="button" className="account-notice__btn" disabled={busy} onClick={() => choose('theirs')}>
            {gone ? '지운 대로 두기' : '다른 기기 내용 쓰기'}
          </button>
        </div>
      </section>
    )
  }

  if (guestToMove > 0) {
    return (
      <section className="account-notice tp-fabric" role="dialog" aria-label="이 기기의 여행 옮기기">
        <b className="account-notice__title">로그인 전에 만든 여행이 {guestToMove}개 있어요</b>
        <p className="account-notice__text">계정으로 옮기면 다른 기기에서도 볼 수 있어요.</p>
        <div className="account-notice__actions">
          <button type="button" className="account-notice__btn account-notice__btn--main" onClick={() => moveGuestTrips(true)}>
            계정으로 옮기기
          </button>
          <button type="button" className="account-notice__btn" onClick={() => moveGuestTrips(false)}>
            이 기기에만 두기
          </button>
        </div>
      </section>
    )
  }

  return null
}
