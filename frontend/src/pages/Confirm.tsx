import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { searchPlaces } from '../api/places'
import type { PlaceOption } from '../api/types'
import { PlaceSearch } from '../components/PlaceSearch'
import { CATEGORY_ICON, DEFAULT_ICON } from '../lib/placeIcons'
import { formatDate, formatTime, tripLength } from '../lib/time'
import { useTrip, type TripItem } from '../store/trip'
import './Confirm.css'

const CATEGORY_LABEL: Record<TripItem['category'], string> = {
  meal: '식사',
  sightseeing: '관광',
  shopping: '쇼핑',
  cafe: '카페',
  transport: '이동',
  other: '기타',
}

// Search result for one item. Missing from the map = still searching.
type Match = { status: 'ok'; options: PlaceOption[] } | { status: 'error' }

export default function Confirm() {
  const { trip, updateItem } = useTrip()
  const [dayIndex, setDayIndex] = useState(0)
  const [matches, setMatches] = useState<Record<string, Match>>({})
  // The place shown for each item before the day is confirmed (first candidate, or the user's tap).
  // Shown is not saved: a place reaches the trip only through "이 날 장소 모두 맞아요".
  const [choice, setChoice] = useState<Record<string, PlaceOption>>({})
  // Item whose candidate list is open ("다른 곳이에요" / "바꾸기").
  const [open, setOpen] = useState<string | null>(null)
  // Items already searched. A ref, so StrictMode's second effect run does not search twice.
  const requested = useRef(new Set<string>())

  const day = trip?.days[dayIndex]

  // Search the places of the day on screen only: other days are searched when opened.
  useEffect(() => {
    if (!trip || !day) return
    for (const it of day.items) {
      if (it.placeId || requested.current.has(it.id)) continue
      requested.current.add(it.id)
      searchPlaces(it.title, trip.city)
        .then(({ candidates }) => {
          setMatches((m) => ({ ...m, [it.id]: { status: 'ok', options: candidates } }))
          const first = candidates[0]
          if (first) setChoice((c) => (c[it.id] ? c : { ...c, [it.id]: first }))
        })
        .catch(() => setMatches((m) => ({ ...m, [it.id]: { status: 'error' } })))
    }
  }, [trip, day])

  if (!trip || !day) {
    return (
      <div className="confirm">
        <div className="confirm__body">
          <p>등록 중인 여행이 없어요.</p>
          <Link className="tp-btn-primary tp-denim" to="/new">
            여행 등록하기
          </Link>
        </div>
      </div>
    )
  }

  const unplaced = (items: TripItem[]) => items.filter((it) => !it.placeId).length
  const totalItems = trip.days.reduce((n, d) => n + d.items.length, 0)
  const totalNeeds = trip.days.reduce((n, d) => n + unplaced(d.items), 0)
  const otherNeeds = totalNeeds - unplaced(day.items)
  const dayReady = day.items.every((it) => it.placeId || choice[it.id])

  function pick(item: TripItem, place: PlaceOption) {
    setChoice((c) => ({ ...c, [item.id]: place }))
    // Changing an already confirmed item saves at once: the user is looking right at it.
    if (item.placeId) updateItem(item.id, { placeId: place.place_id })
    setOpen(null)
  }

  function confirmDay() {
    for (const it of day!.items) {
      const c = choice[it.id]
      if (!it.placeId && c) updateItem(it.id, { placeId: c.place_id })
    }
  }

  function renderPlace(it: TripItem) {
    const match = matches[it.id]
    const shown = choice[it.id]
    const options = match?.status === 'ok' ? match.options : []

    if (open === it.id || (!it.placeId && !shown && match)) {
      // Choosing: candidates (if any) + manual search.
      return (
        <div className="confirm__choose">
          {match?.status === 'error' && <p className="confirm__hint">검색하지 못했어요. 직접 찾아 주세요</p>}
          {match?.status === 'ok' && options.length === 0 && (
            <p className="confirm__hint">“{it.title}”(으)로 찾은 곳이 없어요. 직접 찾아 주세요</p>
          )}
          {options.map((o) => (
            <label className="confirm__option" key={o.place_id}>
              <input
                type="radio"
                name={it.id}
                checked={shown?.place_id === o.place_id}
                onChange={() => pick(it, o)}
              />
              <span>
                <b>{o.name}</b>
                {o.address && <span>{o.address}</span>}
              </span>
            </label>
          ))}
          <PlaceSearch
            inputId={`search-${it.id}`}
            city={trip!.city}
            placeholder="다른 이름으로 찾기"
            picked={null}
            onPick={(o) => pick(it, o)}
          />
        </div>
      )
    }

    if (!match && !it.placeId) return <p className="confirm__hint">장소를 찾고 있어요…</p>

    return (
      <div className="confirm__found">
        <span>
          {/* After a reload only the place_id is kept (no Google names stored): say so plainly. */}
          <b>{shown ? shown.name : '장소 확인됨'}</b>
          {shown?.address && <span>{shown.address}</span>}
        </span>
        <button type="button" onClick={() => setOpen(it.id)}>
          {it.placeId ? '바꾸기' : '다른 곳이에요'}
        </button>
      </div>
    )
  }

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
          <p>붙여넣은 일정마다 장소를 찾아 뒀어요. 다른 곳이면 바꾸고, 맞으면 날마다 한 번 확인해 주세요.</p>
        </div>

        <div className="confirm__summary">
          <div>
            <span>여행</span>
            <b>
              {trip.city} {tripLength(trip.startDate, trip.endDate)}
            </b>
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
          {trip.days.map((d, i) => {
            const n = unplaced(d.items)
            return (
              <button
                key={d.date}
                type="button"
                className="tp-tagstitch"
                aria-current={i === dayIndex ? 'true' : undefined}
                onClick={() => {
                  setDayIndex(i)
                  setOpen(null)
                }}
              >
                DAY {i + 1}
                <span>{n > 0 ? `확인 ${n}` : '확인 끝'}</span>
              </button>
            )
          })}
        </nav>

        <section aria-label={`DAY ${dayIndex + 1} 조각`} className="confirm__list">
          <h2>
            DAY {dayIndex + 1} · {formatDate(day.date)}
          </h2>

          {day.items.map((it) => (
            <div className="confirm__card tp-fabric" key={it.id}>
              <div className="confirm__card-row">
                <img src={CATEGORY_ICON[it.category] ?? DEFAULT_ICON} alt="" aria-hidden="true" />
                <div className="confirm__card-text">
                  <span>
                    {it.start != null ? formatTime(it.start) : '시각 없음'} · {CATEGORY_LABEL[it.category]}
                  </span>
                  <b>{it.title}</b>
                </div>
                {it.placeId && <span className="confirm__chip">확인됨</span>}
              </div>
              {renderPlace(it)}
            </div>
          ))}

          {unplaced(day.items) > 0 && (
            <button type="button" className="tp-btn-primary tp-denim" disabled={!dayReady} onClick={confirmDay}>
              이 날 장소 모두 맞아요
            </button>
          )}
        </section>
      </div>

      <div className="confirm__bar tp-pinked-top">
        {otherNeeds > 0 && <span>다른 날에 확인할 조각이 {otherNeeds}개 더 있어요</span>}
        {totalNeeds === 0 ? (
          <Link className="tp-btn-primary tp-denim" to="/new/grade">
            다음: 중요도 정하기
          </Link>
        ) : (
          <button type="button" className="tp-btn-primary tp-denim" disabled>
            다음: 중요도 정하기
          </button>
        )}
      </div>
    </div>
  )
}
