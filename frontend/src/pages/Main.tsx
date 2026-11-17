import { useState } from 'react'
import { Link } from 'react-router'
import { CATEGORY_LABEL, categoryIcon } from '../lib/category'
import type { Tier } from '../lib/tier'
import { formatDate, formatTime, tripLength } from '../lib/time'
import { useTrip, type TripDay } from '../store/trip'
import './Main.css'

// Hand-placed swatch slots (percent of the map box) for up to 4 stops, copied from the mockup.
const SLOTS = [
  { left: 3, top: 5, w: 36, h: 54, fabric: 'butterfloral' },
  { left: 42, top: 5, w: 26, h: 44, fabric: 'stripe' },
  { left: 71, top: 5, w: 26, h: 44, fabric: 'check' },
  { left: 71, top: 53, w: 26, h: 42, fabric: 'dot' },
] as const

const TIER_LABEL: Record<Tier, string> = { must: '꼭 갈 곳', nice: '좋음', optional: '선택' }

/** The device's own date and clock. A traveller's phone is on local time at the destination. */
function deviceNow(): { date: string; minutes: number } {
  const d = new Date()
  const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return { date, minutes: d.getHours() * 60 + d.getMinutes() }
}

/** First item not finished yet on the day being travelled; on any other day, the first item. */
function nextItem(day: TripDay, isToday: boolean, now: number) {
  const timed = day.items.filter((it) => it.start != null && !it.dropped)
  return isToday ? timed.find((it) => (it.end ?? it.start!) > now) : timed[0]
}

export default function Main() {
  const { trip } = useTrip()
  const [now] = useState(deviceNow)
  const todayIndex = trip ? trip.days.findIndex((d) => d.date === now.date) : -1
  const [dayIndex, setDayIndex] = useState(Math.max(0, todayIndex))

  if (!trip || trip.days.length === 0) {
    return (
      <div className="main-screen">
        <div className="main-screen__head">
          <h1>오늘의 원단</h1>
        </div>
        <section className="main-screen__empty tp-fabric">
          <b>아직 재단한 여행이 없어요</b>
          <span>짜 둔 일정을 붙여넣으면 하루하루를 원단으로 정리해 드려요.</span>
          <Link className="tp-btn-primary tp-denim" to="/new">
            여행 일정 등록하기
          </Link>
        </section>
      </div>
    )
  }

  const day = trip.days[dayIndex]
  const isToday = dayIndex === todayIndex
  const next = nextItem(day, isToday, now.minutes)
  const stops = day.items.filter((it) => !it.dropped).slice(0, SLOTS.length)
  const dayPatches = trip.patches.filter((p) => p.date === day.date)
  const status = (i: number) =>
    i === todayIndex ? '오늘' : now.date < trip.days[i].date ? '다가오는 날' : '지난 날'

  return (
    <div className="main-screen">
      <div className="main-screen__head">
        <span className="main-screen__trip">
          {trip.city} {tripLength(trip.startDate, trip.endDate)}
        </span>
        <div className="main-screen__date">
          {formatDate(day.date)} · DAY {dayIndex + 1} / {trip.days.length}
        </div>
        <h1>{isToday ? '오늘의 원단' : `DAY ${dayIndex + 1}의 원단`}</h1>
      </div>

      <nav className="main-screen__days" aria-label="여행 날짜">
        {trip.days.map((d, i) => (
          <button
            key={d.date}
            type="button"
            className="tp-tagstitch"
            aria-current={i === dayIndex ? 'true' : undefined}
            onClick={() => setDayIndex(i)}
          >
            DAY {i + 1}
            <span>{status(i)}</span>
          </button>
        ))}
      </nav>

      {/* Decorative fabric "map": positions are NOT real locations (real map = Leaflet later). */}
      <section className="main-screen__map" aria-label="원단 지도">
        {stops.map((it, i) => {
          const s = SLOTS[i]
          return (
            <div
              key={it.id}
              className="tp-swatch main-screen__swatch"
              style={{
                left: `${s.left}%`,
                top: `${s.top}%`,
                width: `${s.w}%`,
                height: `${s.h}%`,
                background: `var(--tp-${s.fabric})`,
              }}
            >
              <span>
                {it.start != null && formatTime(it.start)} {it.title}
                {it.id === next?.id && ' · 다음'}
              </span>
              <img src={categoryIcon(it.category)} alt="" aria-hidden="true" />
            </div>
          )
        })}
        <svg aria-hidden="true" viewBox="0 0 100 100" preserveAspectRatio="none">
          <polyline
            points={stops.map((_, i) => `${SLOTS[i].left + SLOTS[i].w / 2},${SLOTS[i].top + SLOTS[i].h / 2}`).join(' ')}
            fill="none"
            stroke="#f4efe4"
            strokeWidth="3"
            strokeDasharray="1 3"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </section>

      {next ? (
        <section className="main-screen__next tp-fabric" aria-label="다음 일정">
          <img src={categoryIcon(next.category)} alt="" aria-hidden="true" />
          <div>
            <span>
              {isToday ? '다음 일정' : '첫 일정'} · <b>{formatTime(next.start!)} 시작</b>
            </span>
            <strong>{next.title}</strong>
            <span>
              {CATEGORY_LABEL[next.category]} · {TIER_LABEL[next.tier]}
              {next.reservationTime != null && ' · 예약'}
            </span>
          </div>
        </section>
      ) : (
        <section className="main-screen__next tp-fabric" aria-label="다음 일정">
          <div>
            <strong>오늘 일정을 모두 마쳤어요</strong>
            <span>{trip.hotel?.title ?? '숙소'}로 돌아갈 시간은 {formatTime(trip.endDeadline)}까지예요.</span>
          </div>
        </section>
      )}

      <section className="main-screen__pieces tp-fabric" aria-label="조각 목록">
        <h2>{isToday ? '오늘의 조각' : '이날의 조각'}</h2>
        {dayPatches.length > 0 && (
          <p className="main-screen__patched">
            덧댄 패치 {dayPatches.length}개 · 마지막 패치로 원래 계획의{' '}
            {Math.floor(dayPatches[dayPatches.length - 1].preservationRate * 100)}%를 지켰어요
          </p>
        )}
        <ul>
          {day.items.map((it) => {
            const isNext = it.id === next?.id
            return (
              <li key={it.id} className={it.dropped ? 'main-screen__piece--dropped' : undefined}>
                <span className={isNext ? 'main-screen__time main-screen__time--next' : 'main-screen__time'}>
                  {it.start != null ? formatTime(it.start) : '--:--'}
                </span>
                <img src={categoryIcon(it.category)} alt="" aria-hidden="true" />
                <span className="main-screen__piece-text">
                  <b>{it.dropped ? <s>{it.title}</s> : it.title}</b>
                  <span>
                    {it.dropped
                      ? '패치로 뺐어요'
                      : `${CATEGORY_LABEL[it.category]} · ${TIER_LABEL[it.tier]}${it.substituted ? ' · 근처 다른 곳' : ''}`}
                  </span>
                </span>
                {isNext && <span className="main-screen__next-tag tp-tagstitch">다음</span>}
                {!isNext && it.patched && !it.dropped && <span className="main-screen__patch-tag">패치</span>}
              </li>
            )
          })}
        </ul>
      </section>

      <div className="main-screen__cta">
        <Link className="tp-btn-primary tp-denim" to="/recover" state={{ dayIndex }}>
          일정이 깨졌어요
        </Link>
        <p>깨진 일정은 직접 알려 주세요.</p>
      </div>
    </div>
  )
}
