import { useState } from 'react'
import { Link } from 'react-router'
import { TierPicker } from '../components/TierPicker'
import { CATEGORY_LABEL, defaultTier } from '../lib/category'
import { itemIcon } from '../lib/placeIcons'
import { formatDate, formatTime } from '../lib/time'
import { useTrip } from '../store/trip'
import { StateCard } from '../components/StateCard'
import { ExitLink } from '../components/ExitLink'
import { StitchLoader } from '../components/StitchLoader'
import { dayLock } from '../lib/tripEdit'
import { useEditTarget } from '../store/editTarget'
import './Grade.css'

const LEGEND: { cls: string; label: string; text: string }[] = [
  { cls: 'must', label: '꼭', text: '빠지면 여행이 아쉬운 곳. 시간을 옮겨서라도 지켜요.' },
  { cls: 'nice', label: '좋음', text: '가고 싶지만, 짧게 들르는 건 괜찮아요.' },
  { cls: 'optional', label: '선택', text: '시간이 남으면 가요. 먼저 빠질 수 있어요.' },
]

// /new/grade: step 2 of registering. /trips/:id/grade: from the edit screen, where past and
// patched days are shown but cannot be changed (lib/tripEdit).
export default function Grade() {
  const { trip, updateItem } = useTrip()
  const { editing, status, today } = useEditTarget()
  const [chosenDay, setOpenDay] = useState<number | null>(null)
  const upcoming = trip?.days.findIndex((d) => d.date >= today) ?? -1
  const openDay = chosenDay ?? (editing ? Math.max(0, upcoming) : 0)

  if (status === 'loading') return <StitchLoader steps={['여행을 불러오고 있어요']} />

  if (status === 'missing' || !trip) {
    return (
      <StateCard
        kind="empty"
        title="등록 중인 여행이 없어요"
        actions={
          <Link className="tp-btn-primary tp-denim" to="/new">
            여행 등록하기
          </Link>
        }
      >
        <p>짜 둔 일정을 붙여넣으면 여기서 장소와 시간을 확인해요.</p>
      </StateCard>
    )
  }

  return (
    <div className="grade">
      {!editing && (
        <>
          <div className="grade__step">
            <span>중요도 정하기</span>
            <span>2 / 2</span>
          </div>
          <div className="grade__progress" aria-hidden="true" />
        </>
      )}

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

        {trip.days.map((day, di) => {
          const label = `DAY ${di + 1}`
          const changed = day.items.filter((it) => it.tier !== defaultTier(it)).length
          if (di !== openDay) {
            return (
              <button type="button" key={day.date} className="grade__collapsed tp-fabric" onClick={() => setOpenDay(di)}>
                <span>
                  <b>{label}</b> · 조각 {day.items.length}개
                </span>
                <span>{changed > 0 ? `직접 바꿈 ${changed} · 펼치기` : '추천대로 · 펼치기'}</span>
              </button>
            )
          }
          const lock = editing ? dayLock(trip, day.date, today) : null
          return (
            <section key={day.date} aria-label={`${label} 조각 중요도`} className="grade__list">
              <h2>
                {label} · {formatDate(day.date)}
              </h2>
              {lock && (
                <p className="grade__locked">
                  {lock === 'past' ? '지난 날은 바꿀 수 없어요.' : '패치를 덧댄 날이에요. 여행 고치기에서 패치를 풀면 바꿀 수 있어요.'}
                </p>
              )}
              {day.items.map((it) => {
                const recommended = defaultTier(it)
                const edited = it.tier !== recommended
                return (
                  <fieldset
                    key={it.id}
                    disabled={lock !== null}
                    className={`grade__item tp-fabric${edited ? ' grade__item--edited' : ''}`}
                  >
                    <legend className="sr-only">{it.title} 중요도</legend>
                    <div className="grade__item-head">
                      <img src={itemIcon(it)} alt="" aria-hidden="true" />
                      <span>
                        <b>{it.title}</b>
                        <span>
                          {it.start != null ? formatTime(it.start) : '시각 없음'} · {CATEGORY_LABEL[it.category]}
                          {it.reservationTime != null && ' · 예약'}
                        </span>
                      </span>
                      {edited && <em>직접 바꿈</em>}
                    </div>
                    <TierPicker
                      name={it.id}
                      value={it.tier}
                      recommended={recommended}
                      onChange={(tier) => updateItem(it.id, { tier })}
                    />
                  </fieldset>
                )
              })}
            </section>
          )
        })}
      </div>

      <div className="grade__bar tp-pinked-top">
        <span>{editing ? '바꾸면 바로 저장돼요' : '나중에 여행 고치기에서도 바꿀 수 있어요'}</span>
        {/* Done: leave the flow, so back does not walk through its steps again. */}
        <ExitLink flow="new" className="tp-btn-primary tp-denim">
          {editing ? '다 고쳤어요' : '원단 완성하기'}
        </ExitLink>
      </div>
    </div>
  )
}
