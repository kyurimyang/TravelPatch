import { useState } from 'react'
import { Link, useLocation } from 'react-router'
import { TierPicker } from '../components/TierPicker'
import type { Tier } from '../lib/tier'
import { PLACE_ICONS } from '../lib/placeIcons'
import { MOCK_DAYS, type DraftItemView } from '../mocks/draftItinerary'
import './Grade.css'

const LEGEND: { cls: string; label: string; text: string }[] = [
  { cls: 'must', label: '꼭', text: '빠지면 여행이 아쉬운 곳. 시간을 옮겨서라도 지켜요.' },
  { cls: 'nice', label: '좋음', text: '가고 싶지만, 짧게 들르는 건 괜찮아요.' },
  { cls: 'optional', label: '선택', text: '시간이 남으면 가요. 먼저 빠질 수 있어요.' },
]

// Confirm passes the candidate the user picked for ambiguous items (itemId -> candidateId).
type ConfirmState = { picked?: Record<string, string> } | null

export default function Grade() {
  const picked = (useLocation().state as ConfirmState)?.picked ?? {}

  // itemId -> tier. Starts from the recommended tier (source = llm_default); any difference is "user".
  const [tiers, setTiers] = useState<Record<string, Tier>>(() =>
    Object.fromEntries(MOCK_DAYS.flatMap((d) => d.items.map((it) => [it.id, it.recommendedTier]))),
  )
  const [openDay, setOpenDay] = useState(0)

  const nameOf = (it: DraftItemView) =>
    it.match === 'found'
      ? it.name
      : (it.candidates!.find((c) => c.id === picked[it.id]) ?? it.candidates![0]).name

  return (
    <div className="grade">
      <div className="grade__step">
        <span>중요도 정하기</span>
        <span>2 / 2</span>
      </div>
      <div className="grade__progress" aria-hidden="true" />

      <div className="grade__body">
        <div className="grade__intro">
          <h1>
            꼭 지킬 조각을
            <br />
            알려 주세요
          </h1>
          <p>
            일정이 깨지면 ‘꼭’은 최대한 지키고, ‘선택’부터 줄이거나 빼요. 먼저 골라 뒀으니 다르면 눌러서 바꿔 주세요.
          </p>
        </div>

        <div className="grade__legend tp-fabric">
          {LEGEND.map((l) => (
            <div key={l.cls}>
              <span className={`grade__pill grade__pill--${l.cls}`}>{l.label}</span>
              <span>{l.text}</span>
            </div>
          ))}
        </div>

        {MOCK_DAYS.map((day, di) => {
          const changed = day.items.filter((it) => tiers[it.id] !== it.recommendedTier).length
          if (di !== openDay) {
            return (
              <button type="button" key={day.label} className="grade__collapsed tp-fabric" onClick={() => setOpenDay(di)}>
                <span>
                  <b>{day.label}</b> · 조각 {day.items.length}개
                </span>
                <span>{changed > 0 ? `직접 바꿈 ${changed} · 펼치기` : '추천대로 · 펼치기'}</span>
              </button>
            )
          }
          return (
            <section key={day.label} aria-label={`${day.label} 조각 중요도`} className="grade__list">
              <h2>
                {day.label} · {day.dateLabel}
              </h2>
              {day.items.map((it) => {
                const edited = tiers[it.id] !== it.recommendedTier
                return (
                  <fieldset
                    key={it.id}
                    className={`grade__item tp-fabric${edited ? ' grade__item--edited' : ''}`}
                  >
                    <legend className="sr-only">{nameOf(it)} 중요도</legend>
                    <div className="grade__item-head">
                      <img src={PLACE_ICONS[it.icon]} alt="" aria-hidden="true" />
                      <span>
                        <b>{nameOf(it)}</b>
                        <span>
                          {it.time} · {it.categoryLabel}
                        </span>
                      </span>
                      {edited && <em>직접 바꿈</em>}
                    </div>
                    <TierPicker
                      name={it.id}
                      value={tiers[it.id]}
                      recommended={it.recommendedTier}
                      onChange={(t) => setTiers((prev) => ({ ...prev, [it.id]: t }))}
                    />
                  </fieldset>
                )
              })}
            </section>
          )
        })}
      </div>

      <div className="grade__bar tp-pinked-top">
        <span>나중에 일정 화면에서도 바꿀 수 있어요</span>
        {/* Goes to Main. No location-permission screen: GPS is out of MVP (2026-11-17). */}
        <Link className="tp-btn-primary tp-denim" to="/">
          원단 완성하기
        </Link>
      </div>
    </div>
  )
}
