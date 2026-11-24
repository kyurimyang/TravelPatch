import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { formatTime, tripLength } from '../lib/time'
import { deviceNow, needsCheck, nextItem, tripPhase, type TripPhase } from '../lib/today'
import { useTrip, type Trip } from '../store/trip'
import { StateCard } from '../components/StateCard'
import './TripList.css'

const SECTION: Record<TripPhase, string> = { ongoing: '진행 중', upcoming: '다가오는 여행', past: '지난 여행' }

/** "10월 7일 – 10월 10일" (UTC: the trip's own calendar days, whatever the viewer's zone). */
function dateRange(trip: Trip): string {
  const f = new Intl.DateTimeFormat('ko-KR', { month: 'long', day: 'numeric', timeZone: 'UTC' })
  return `${f.format(new Date(`${trip.startDate}T00:00:00Z`))} – ${f.format(new Date(`${trip.endDate}T00:00:00Z`))}`
}

export default function TripList() {
  const navigate = useNavigate()
  const { trips, trip: current, selectTrip, deleteTrip } = useTrip()
  const [now] = useState(deviceNow)
  const [confirming, setConfirming] = useState<string | null>(null)

  const phases = new Map(trips.map((t) => [t.id, tripPhase(t, now.date)]))
  const ongoing = trips.filter((t) => phases.get(t.id) === 'ongoing').length

  function open(id: string) {
    selectTrip(id)
    navigate('/')
  }

  // A trip is a boarding pass (2026-11-24, like the logo): the main part says where and when,
  // the stub says where you are in it. One tag style, no empty box, delete as a small icon.
  function card(t: Trip) {
    const phase = phases.get(t.id)!
    const todayIndex = t.days.findIndex((d) => d.date === now.date)
    const today = todayIndex >= 0 ? t.days[todayIndex] : null
    const next = today ? nextItem(today, true, now.minutes) : null
    const checks = needsCheck(t)
    const until = Math.round((Date.parse(t.startDate) - Date.parse(now.date)) / 86_400_000)

    return (
      <li key={t.id} className={`trip-card trip-card--${phase}`}>
        <button type="button" className="trip-card__open" onClick={() => open(t.id)}>
          <span className="trip-card__main">
            {t.id === current?.id && <span className="trip-card__current">지금 보는 여행</span>}
            <b className="trip-card__title">{t.city}</b>
            <span className="trip-card__sub">
              {dateRange(t)} · {tripLength(t.startDate, t.endDate)}
            </span>
            <span className="trip-card__days" aria-hidden="true">
              {t.days.map((d, i) => (
                <i
                  key={d.date}
                  data-state={
                    phase === 'past' || (todayIndex >= 0 && i < todayIndex) ? 'done' : i === todayIndex ? 'today' : 'ahead'
                  }
                />
              ))}
            </span>
            {next && (
              <span className="trip-card__next">
                다음 <b>{formatTime(next.start!)}</b> {next.title}
              </span>
            )}
            {checks > 0 && <span className="trip-card__chip trip-card__chip--warn">확인 필요 {checks}</span>}
          </span>
          <span className="trip-card__stub">
            {phase === 'ongoing' && todayIndex >= 0 ? (
              <>
                <span className="trip-card__stub-label">DAY</span>
                <b>
                  {todayIndex + 1}
                  <small>/{t.days.length}</small>
                </b>
              </>
            ) : phase === 'upcoming' ? (
              <>
                <span className="trip-card__stub-label">출발까지</span>
                <b>D-{Math.max(until, 0)}</b>
              </>
            ) : (
              <>
                <span className="trip-card__stub-label">여행</span>
                <b className="trip-card__stub-word">완성</b>
              </>
            )}
            {t.patches.length > 0 && <span className="trip-card__patches">패치 {t.patches.length}</span>}
          </span>
        </button>
        {confirming === t.id ? (
          <span className="trip-card__confirm" role="alert">
            이 여행과 패치 기록을 지울까요?
            <button type="button" onClick={() => (deleteTrip(t.id), setConfirming(null))}>
              지우기
            </button>
            <button type="button" onClick={() => setConfirming(null)}>
              그대로 두기
            </button>
          </span>
        ) : (
          <button type="button" className="trip-card__delete" aria-label={`${t.city} 여행 지우기`} onClick={() => setConfirming(t.id)}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 7h16M9 7V4.5h6V7M6.5 7l1 12.5h9l1-12.5M10 11v5M14 11v5" />
            </svg>
          </button>
        )}
      </li>
    )
  }

  return (
    <section className="trip-list">
      <div className="trip-list__head">
        <h1>내 여행</h1>
        <span>
          여행 {trips.length}개{ongoing > 0 && ` · 진행 중 ${ongoing}개`}
        </span>
      </div>

      {trips.length === 0 && (
        <StateCard kind="empty" title="아직 재단한 여행이 없어요">
          <p>짜 둔 일정을 붙여넣으면 여행 원단으로 정리해 드려요.</p>
        </StateCard>
      )}

      {(['ongoing', 'upcoming', 'past'] as const).map((phase) => {
        const list = trips.filter((t) => phases.get(t.id) === phase)
        if (list.length === 0) return null
        return (
          <div key={phase} className="trip-list__group">
            <h2>{SECTION[phase]}</h2>
            <ul>{list.map(card)}</ul>
          </div>
        )
      })}

      <Link className="tp-btn-primary tp-denim trip-list__new" to="/new">
        새 여행 만들기
      </Link>
    </section>
  )
}
