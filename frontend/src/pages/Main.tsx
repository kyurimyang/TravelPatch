import { useState } from 'react'
import { Link } from 'react-router'
import { HoleAlert, isLate } from '../components/HoleAlert'
import { CATEGORY_LABEL } from '../lib/category'
import { itemIcon } from '../lib/placeIcons'
import type { Tier } from '../lib/tier'
import { formatDate, formatTime, tripLength } from '../lib/time'
import { deviceNow, needsCheck, nextItem } from '../lib/today'
import { quilt } from '../lib/quilt'
import { dayKept } from '../lib/kept'
import { useTrip } from '../store/trip'
import { StateCard } from '../components/StateCard'
import './Main.css'


const TIER_LABEL: Record<Tier, string> = { must: '꼭 갈 곳', nice: '좋음', optional: '선택' }

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
        <StateCard
          kind="empty"
          title="아직 재단한 여행이 없어요"
          actions={
            <Link className="tp-btn-primary tp-denim" to="/new">
              여행 일정 등록하기
            </Link>
          }
        >
          <p>짜 둔 일정을 붙여넣으면 하루하루를 원단으로 정리해 드려요.</p>
        </StateCard>
      </div>
    )
  }

  const day = trip.days[dayIndex]
  const isToday = dayIndex === todayIndex
  const next = nextItem(day, isToday, now.minutes)
  // Up to 6 pieces of the day on the quilt; its cut and cloth change every day (lib/quilt).
  const stops = day.items.filter((it) => !it.dropped).slice(0, 6)
  const pieces = quilt(stops.length, `${trip.id}:${day.date}`)
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

      {/* Settling places/times can wait past registration (Confirm, 2026-11-23); say what is left. */}
      {needsCheck(trip) > 0 && (
        <Link className="main-screen__todo tp-fabric" to="/new/confirm" state={{ reopened: true }}>
          <span>확인 안 한 조각 {needsCheck(trip)}개</span>
          <b>일정 확인하기</b>
        </Link>
      )}

      {isToday && isLate(next, now.minutes) && (
        <HoleAlert
          dayIndex={dayIndex}
          next={next}
          following={day.items.filter((it) => !it.dropped && it.start != null && it.start > next.start!).length}
          now={now.minutes}
        />
      )}

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

      {/* Decorative fabric "map": positions are NOT real locations (real map = Leaflet later).
          A quilt of the day's pieces: cut and cloth change every day (lib/quilt). No route line
          drawn across it: it covered the labels (2026-11-24); the times give the order. */}
      <section
        className={`main-screen__map${stops.length > 4 ? ' main-screen__map--tall' : ''}`}
        aria-label="원단 지도"
      >
        {pieces.map((p, pi) => {
          const it = p.stop === null ? null : stops[p.stop]
          const place = {
            left: `${p.box.left}%`,
            top: `${p.box.top}%`,
            width: `${p.box.width}%`,
            height: `${p.box.height}%`,
          }
          const cloth = (
            <i style={{ background: `var(--tp-${p.fabric})`, transform: `rotate(${p.tilt}deg)` }} aria-hidden="true" />
          )
          if (!it) {
            return (
              <div key={`scrap-${pi}`} className="main-screen__swatch main-screen__swatch--scrap" style={place}>
                {cloth}
              </div>
            )
          }
          return (
            <div
              key={it.id}
              className="main-screen__swatch"
              data-next={it.id === next?.id ? 'true' : undefined}
              style={place}
            >
              {cloth}
              <span className="main-screen__label">
                {it.start != null && (
                  <b>
                    {formatTime(it.start)}
                    {it.id === next?.id && ' · 다음'}
                  </b>
                )}
                <span>{it.title}</span>
              </span>
              <img src={itemIcon(it)} alt="" aria-hidden="true" />
            </div>
          )
        })}
      </section>

      {next ? (
        <section className="main-screen__next tp-fabric" aria-label="다음 일정">
          <img src={itemIcon(next)} alt="" aria-hidden="true" />
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
            {/* Against the day as first planned, not the last patch's own rate (lib/kept.ts). */}
            덧댄 패치 {dayPatches.length}개 · 이날 원래 계획의 {Math.floor(dayKept(trip, day.date) * 100)}%가 남아 있어요
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
                <img src={itemIcon(it)} alt="" aria-hidden="true" />
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
