import { useState } from 'react'
import { Link, useLocation } from 'react-router'
import { PLACE_ICONS } from '../lib/placeIcons'
import { MOCK_DAYS, MOCK_TRIP_TITLE } from '../mocks/draftItinerary'
import './Confirm.css'

// What Landing passes along (see Landing.tsx). Missing when the URL is opened directly.
type LandingState = { city: string; start: string; end: string; text: string } | null

function tripTitle(s: LandingState): string {
  if (!s) return MOCK_TRIP_TITLE
  const nights = Math.round((Date.parse(s.end) - Date.parse(s.start)) / 86_400_000)
  return `${s.city} ${nights}박 ${nights + 1}일`
}

export default function Confirm() {
  const state = useLocation().state as LandingState
  const [dayIndex, setDayIndex] = useState(0)
  // itemId -> chosen candidate id. An ambiguous item stays "needs checking" until it has an entry.
  const [picked, setPicked] = useState<Record<string, string>>({})

  const needsCheck = (dayItems: (typeof MOCK_DAYS)[number]['items']) =>
    dayItems.filter((it) => it.match === 'ambiguous' && !picked[it.id]).length

  const day = MOCK_DAYS[dayIndex]
  const totalItems = MOCK_DAYS.reduce((n, d) => n + d.items.length, 0)
  const totalNeeds = MOCK_DAYS.reduce((n, d) => n + needsCheck(d.items), 0)
  const otherNeeds = totalNeeds - needsCheck(day.items)

  return (
    <div className="confirm">
      <div className="confirm__step">
        <span>일정 확인</span>
        <span>1 / 2</span>
      </div>
      <div className="confirm__progress" aria-hidden="true">
        <div style={{ width: '50%' }} />
      </div>

      <div className="confirm__body">
        <div className="confirm__intro">
          <h1>이렇게 재단했어요</h1>
          <p>붙여넣은 일정을 장소와 시간으로 나눴어요. 틀린 곳만 고쳐 주세요.</p>
        </div>

        <div className="confirm__summary">
          <div>
            <span>여행</span>
            <b>{tripTitle(state)}</b>
          </div>
          <div>
            <span>조각</span>
            <b>{totalItems}개</b>
          </div>
          <div className={totalNeeds > 0 ? 'confirm__summary--warn' : undefined}>
            <span>확인 필요</span>
            <b>{totalNeeds}개</b>
          </div>
        </div>

        <nav className="confirm__days" aria-label="여행 날짜">
          {MOCK_DAYS.map((d, i) => {
            const n = needsCheck(d.items)
            return (
              <button
                key={d.label}
                type="button"
                className="tp-tagstitch"
                aria-current={i === dayIndex ? 'true' : undefined}
                onClick={() => setDayIndex(i)}
              >
                {d.label}
                <span>{n > 0 ? `확인 ${n}` : '확인 끝'}</span>
              </button>
            )
          })}
        </nav>

        <section aria-label={`${day.label} 조각`} className="confirm__list">
          <h2>
            {day.label} · {day.dateLabel}
          </h2>

          {day.items.map((it) =>
            it.match === 'found' || picked[it.id] ? (
              <div className="confirm__card tp-fabric" key={it.id}>
                <img src={PLACE_ICONS[it.icon]} alt="" aria-hidden="true" />
                <div className="confirm__card-text">
                  <span>
                    {it.time} · 붙여넣은 글 “{it.rawText}”
                  </span>
                  <b>{it.match === 'found' ? it.name : it.candidates!.find((c) => c.id === picked[it.id])!.name}</b>
                  <span>
                    {it.categoryLabel}
                    {it.address && ` · ${it.address}`}
                  </span>
                </div>
                <span className="confirm__chip">찾았어요</span>
              </div>
            ) : (
              <fieldset className="confirm__ambiguous tp-fabric" key={it.id}>
                <legend>확인 필요 · 비슷한 곳이 {it.candidates!.length}군데예요</legend>
                <div className="confirm__card-row">
                  <img src={PLACE_ICONS[it.icon]} alt="" aria-hidden="true" />
                  <div className="confirm__card-text">
                    <span>
                      {it.time} · 붙여넣은 글 “{it.rawText}”
                    </span>
                    <b>{it.name}</b>
                  </div>
                </div>
                {it.candidates!.map((c) => (
                  <label className="confirm__option" key={c.id}>
                    <input
                      type="radio"
                      name={it.id}
                      onChange={() => setPicked((p) => ({ ...p, [it.id]: c.id }))}
                    />
                    <span>
                      <b>{c.name}</b>
                      <span>{c.sub}</span>
                    </span>
                  </label>
                ))}
                {/* Manual search needs the Places API (stage 6). */}
                <button type="button" className="confirm__manual" disabled>
                  둘 다 아니에요, 직접 찾을게요
                </button>
              </fieldset>
            ),
          )}

          <button type="button" className="confirm__add" disabled>
            + 조각 추가하기
          </button>
        </section>
      </div>

      <div className="confirm__bar tp-pinked-top">
        {otherNeeds > 0 && <span>다른 날에 확인할 조각이 {otherNeeds}개 더 있어요</span>}
        <Link className="tp-btn-primary tp-denim" to="/new/grade" state={{ picked }}>
          다음: 중요도 정하기
        </Link>
      </div>
    </div>
  )
}
