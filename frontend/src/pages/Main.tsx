import { useState } from 'react'
import { Link } from 'react-router'
import { PLACE_ICONS } from '../lib/placeIcons'
import type { Tier } from '../lib/tier'
import { MOCK_DAYS, MOCK_TRIP_TITLE } from '../mocks/draftItinerary'
import './Main.css'

// Hand-placed swatch slots (percent of the map box) for up to 4 stops, copied from the mockup.
const SLOTS = [
  { left: 3, top: 5, w: 36, h: 54, fabric: 'butterfloral' },
  { left: 42, top: 5, w: 26, h: 44, fabric: 'stripe' },
  { left: 71, top: 5, w: 26, h: 44, fabric: 'check' },
  { left: 71, top: 53, w: 26, h: 42, fabric: 'dot' },
] as const

const TIER_LABEL: Record<Tier, string> = { must: '꼭 갈 곳', nice: '좋음', optional: '선택' }

// Mock "today" = DAY 1. The real value must come from the trip dates + current time passed in.
const TODAY_INDEX = 0

export default function Main() {
  const [dayIndex, setDayIndex] = useState(TODAY_INDEX)
  const day = MOCK_DAYS[dayIndex]
  const stops = day.items.slice(0, SLOTS.length)
  const next = day.items[0]

  return (
    <div className="main-screen">
      <div className="main-screen__head">
        {/* Trip switching belongs to TripList (stage 4); shown as a label only for now. */}
        <span className="main-screen__trip">{MOCK_TRIP_TITLE}</span>
        <div className="main-screen__date">
          {day.dateLabel} · {day.label} / {MOCK_DAYS.length}
        </div>
        <h1>오늘의 원단</h1>
      </div>

      <nav className="main-screen__days" aria-label="여행 날짜">
        {MOCK_DAYS.map((d, i) => (
          <button
            key={d.label}
            type="button"
            className="tp-tagstitch"
            aria-current={i === dayIndex ? 'true' : undefined}
            onClick={() => setDayIndex(i)}
          >
            {d.label}
            <span>{i === TODAY_INDEX ? '오늘' : '재단됨'}</span>
          </button>
        ))}
      </nav>

      {/* Decorative fabric "map": positions are NOT real locations (real map = Leaflet later). */}
      <section className="main-screen__map" aria-label="오늘의 원단 지도">
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
                {it.time} {it.name}
                {i === 0 && ' · 다음'}
              </span>
              <img src={PLACE_ICONS[it.icon]} alt="" aria-hidden="true" />
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

      {/* No travel time shown: it needs the Routes API (stage 6). Only what the plan itself knows. */}
      <section className="main-screen__next tp-fabric" aria-label="다음 일정">
        <img src={PLACE_ICONS[next.icon]} alt="" aria-hidden="true" />
        <div>
          <span>
            다음 일정 · <b>{next.time} 시작</b>
          </span>
          <strong>{next.name}</strong>
          <span>
            {next.categoryLabel}
            {next.address && ` · ${next.address}`}
          </span>
        </div>
      </section>

      <section className="main-screen__pieces tp-fabric" aria-label="오늘의 조각">
        <h2>오늘의 조각</h2>
        <ul>
          {day.items.map((it, i) => (
            <li key={it.id}>
              <span className={i === 0 ? 'main-screen__time main-screen__time--next' : 'main-screen__time'}>
                {it.time}
              </span>
              <img src={PLACE_ICONS[it.icon]} alt="" aria-hidden="true" />
              <span className="main-screen__piece-text">
                <b>{it.name}</b>
                <span>
                  {it.categoryLabel} · {TIER_LABEL[it.recommendedTier]}
                </span>
              </span>
              {i === 0 && <span className="main-screen__next-tag tp-tagstitch">다음</span>}
            </li>
          ))}
        </ul>
      </section>

      <div className="main-screen__cta">
        <Link className="tp-btn-primary tp-denim" to="/recover">
          일정이 깨졌어요
        </Link>
        <p>깨진 일정은 직접 알려 주세요.</p>
      </div>
    </div>
  )
}
