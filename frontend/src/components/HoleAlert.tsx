import { useState } from 'react'
import { Link } from 'react-router'
import { formatTime } from '../lib/time'
import type { TripItem } from '../store/trip'
import './HoleAlert.css'

/** Minutes past an item's start before we ask. Short waits are normal; we do not nag. */
export const LATE_AFTER_MIN = 10
const DISMISS_KEY = 'trippatch.hole.dismissed'

type Props = {
  dayIndex: number
  next: TripItem
  /** Items after `next` that the delay would push. */
  following: number
  now: number
}

function dismissed(): string[] {
  try {
    return JSON.parse(sessionStorage.getItem(DISMISS_KEY) ?? '[]') as string[]
  } catch {
    return []
  }
}

/** Should Main ask? Only on the day being travelled, when the next item's start has passed. */
export function isLate(next: TripItem | undefined, now: number): next is TripItem {
  return !!next && next.start != null && now - next.start >= LATE_AFTER_MIN && !dismissed().includes(next.id)
}

// "구멍 발견" without GPS or live transit (both out of MVP): the clock says the next piece should
// have started a while ago, so we ask instead of assuming.
export function HoleAlert({ dayIndex, next, following, now }: Props) {
  const [hidden, setHidden] = useState(false)
  if (hidden) return null
  const late = now - next.start!

  function keep() {
    try {
      sessionStorage.setItem(DISMISS_KEY, JSON.stringify([...dismissed(), next.id]))
    } catch {
      // without storage we only hide it for this view
    }
    setHidden(true)
  }

  return (
    <section className="hole-alert" aria-label="구멍 발견" role="alert">
      <span className="hole-alert__tag tp-tagstitch">풀린 실</span>
      <h2>
        오늘의 원단에
        <br />
        구멍이 났나요?
      </h2>
      <p>
        ‘{next.title}’ 시작({formatTime(next.start!)})이 {late}분 지났어요. 늦어지고 있다면 뒤 일정을 맞춰 드릴게요.
      </p>
      <div className="hole-alert__stats">
        <div>
          <span>구멍 크기</span>
          <b>약 {late}분</b>
        </div>
        <div>
          <span>풀릴 수 있는 실</span>
          <b>뒤 일정 {following}개</b>
        </div>
      </div>
      <Link
        className="tp-btn-primary tp-denim"
        to="/recover"
        // The late piece, not a sentence: Recover builds the event itself (A2). A "18분 늦어요"
        // sentence would be read as 18 more minutes on top of now, which already holds them.
        state={{ dayIndex, hole: next.id }}
      >
        수선하기
      </Link>
      <div className="hole-alert__more">
        <Link to="/recover" state={{ dayIndex }}>
          다른 상황이에요
        </Link>
        <button type="button" onClick={keep}>
          그대로 둘게요
        </button>
      </div>
    </section>
  )
}
