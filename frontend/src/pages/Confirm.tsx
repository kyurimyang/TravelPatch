import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { searchPlaces } from '../api/places'
import type { PlaceOption } from '../api/types'
import { PlaceSearch } from '../components/PlaceSearch'
import { TimeEditor } from '../components/TimeEditor'
import { CATEGORY_LABEL } from '../lib/category'
import { itemIcon } from '../lib/placeIcons'
import { formatDate, formatTime, parseTime, tripLength } from '../lib/time'
import { useTrip, type DraftIssue, type TripItem } from '../store/trip'
import { withJosa } from '../lib/josa'
import { StateCard } from '../components/StateCard'
import './Confirm.css'

// What the parser could not settle, in the user's words. Shown until the item has a usable range.
const ISSUE_TEXT: Record<DraftIssue['code'], string> = {
  NO_TIME: '시각이 적혀 있지 않아요',
  MISSING_START: '끝나는 시각만 있어요',
  BAD_TIME: '시각을 읽지 못했어요',
  BAD_RANGE: '끝나는 시각이 시작보다 빨라요',
  RESERVED_NO_TIME: '예약이라고 적혀 있는데 시각이 없어요',
  OVER_MIDNIGHT: '자정을 넘겨요',
  OUT_OF_ORDER: '',
  OVERLAP: '',
}

// The engine can use an item only with a start and a later end (same rule as its Activity model).
// Judged from the item itself, not from the parser's issue list, which goes stale once the user edits.
const hasTime = (it: TripItem) => it.start != null && it.end != null && it.end > it.start

// Search result for one item. Missing from the map = still searching.
type Match = { status: 'ok'; options: PlaceOption[] } | { status: 'error' }

export default function Confirm() {
  const { trip, setTrip, updateItem } = useTrip()
  const [dayIndex, setDayIndex] = useState(0)
  const [matches, setMatches] = useState<Record<string, Match>>({})
  // Google's name for each picked place, for this screen only (names are never saved).
  // The first candidate is saved at once (decision 2026-11-18): the user only fixes wrong ones.
  const [choice, setChoice] = useState<Record<string, PlaceOption>>({})
  // Item whose candidate list is open ("다른 곳이에요" / "바꾸기").
  const [open, setOpen] = useState<string | null>(null)
  // Item whose time editor is open (items without a usable time always show it).
  const [editing, setEditing] = useState<string | null>(null)
  // Items already searched. A ref, so StrictMode's second effect run does not search twice.
  const requested = useRef(new Set<string>())

  const day = trip?.days[dayIndex]

  // Search the places of the day on screen only: other days are searched when opened.
  useEffect(() => {
    if (!trip || !day) return
    for (const it of day.items) {
      if (it.placeId || requested.current.has(it.id)) continue
      requested.current.add(it.id)
      searchPlaces(it.placeQuery || it.title, trip.city, trip.hotel?.placeId)
        .then(({ candidates }) => {
          setMatches((m) => ({ ...m, [it.id]: { status: 'ok', options: candidates } }))
          const first = candidates[0]
          if (!first) return
          setChoice((c) => ({ ...c, [it.id]: first }))
          updateItem(it.id, { placeId: first.place_id })
        })
        .catch(() => setMatches((m) => ({ ...m, [it.id]: { status: 'error' } })))
    }
  }, [trip, day, updateItem])

  if (!trip || !day) {
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

  const needs = (items: TripItem[]) => items.filter((it) => !it.placeId || !hasTime(it)).length
  const totalItems = trip.days.reduce((n, d) => n + d.items.length, 0)
  const totalNeeds = trip.days.reduce((n, d) => n + needs(d.items), 0)
  const otherNeeds = totalNeeds - needs(day.items)
  function pick(item: TripItem, place: PlaceOption) {
    // The user chose it themselves: no "far from the hotel" second look.
    setChoice((c) => ({ ...c, [item.id]: { ...place, far: null } }))
    updateItem(item.id, { placeId: place.place_id })
    setOpen(null)
  }

  // Hotel and airport lines were linked at registration (tripFromDraft): name them by the user's words.
  function knownLabel(it: TripItem): string | null {
    const t = trip!
    if (t.hotel && it.placeId === t.hotel.placeId) return `숙소 · ${t.hotel.title}`
    for (const f of [t.arrival, t.departure]) {
      if (f && it.placeId === f.airport.placeId) return `공항 · ${f.airport.title}`
    }
    return null
  }

  function saveTime(item: TripItem, index: number, start: number, end: number) {
    // A line marked as booked but without a time lost its booking on the server (no time to hold);
    // the issue still says so, so the booking comes back with the time the user gives.
    const wasReserved = day!.issues.some((i) => i.item === index && i.code === 'RESERVED_NO_TIME')
    const reserved = item.reservationTime != null || wasReserved
    updateItem(item.id, { start, end, durationEstimated: false, reservationTime: reserved ? start : null })
    setEditing(null)
  }

  function renderTime(it: TripItem, index: number, prev: TripItem | undefined) {
    const ready = hasTime(it)
    const problem = day!.issues.find((i) => i.item === index && ISSUE_TEXT[i.code])
    const overlaps = ready && prev && hasTime(prev) && it.start! < prev.end!

    if (!ready || editing === it.id) {
      return (
        <div className="confirm__time">
          {!ready && <p className="confirm__warn">{problem ? ISSUE_TEXT[problem.code] : '시각을 정해 주세요'}</p>}
          <TimeEditor
            idPrefix={`time-${it.id}`}
            start={it.start}
            end={it.end}
            onSave={(s, e) => saveTime(it, index, s, e)}
            onCancel={ready ? () => setEditing(null) : undefined}
          />
        </div>
      )
    }
    return (
      <>
        {it.durationEstimated && (
          <p className="confirm__hint">끝나는 시각은 짐작한 값이에요 (약 {it.end! - it.start!}분)</p>
        )}
        {overlaps && <p className="confirm__hint">앞 일정과 시간이 겹쳐요. 맞는지 확인해 주세요</p>}
        <button type="button" className="confirm__link" onClick={() => setEditing(it.id)}>
          시각 고치기
        </button>
      </>
    )
  }

  function renderPlace(it: TripItem) {
    const match = matches[it.id]
    const shown = choice[it.id]
    const options = match?.status === 'ok' ? match.options : []

    if (open === it.id || (!it.placeId && match)) {
      // Choosing: candidates (if any) + manual search.
      return (
        <div className="confirm__choose">
          {match?.status === 'error' && <p className="confirm__hint">검색하지 못했어요. 직접 찾아 주세요</p>}
          {match?.status === 'ok' && options.length === 0 && (
            <p className="confirm__hint">{withJosa(`“${it.title}”`, '으로/로')} 찾은 곳이 없어요. 직접 찾아 주세요</p>
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
      <>
        {/* Non-blocking: a far hit is often the wrong branch, but a day trip is far on purpose. */}
        {shown?.far && <p className="confirm__warn">숙소에서 20km 넘게 떨어진 곳이에요. 맞는지 봐 주세요</p>}
        <div className="confirm__found">
          <span>
            {/* After a reload only the place_id is kept (no Google names stored): say so plainly. */}
            <b>{shown ? shown.name : (knownLabel(it) ?? '장소 확인됨')}</b>
            {shown?.address && <span>{shown.address}</span>}
          </span>
          <button type="button" onClick={() => setOpen(it.id)}>
            바꾸기
          </button>
        </div>
      </>
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
          <p>장소는 찾아서 채워 뒀어요. 다른 곳만 바꾸고, 표시된 것만 고쳐 주세요.</p>
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

        <div className="confirm__deadline tp-fabric">
          <label htmlFor="deadline">
            <b>숙소로 돌아올 시각</b>
            <span>{trip.hotel?.title ?? '숙소'} · 일정이 깨져도 이 시각은 지켜요</span>
          </label>
          <input
            id="deadline"
            type="time"
            step={300}
            value={formatTime(trip.endDeadline)}
            onChange={(e) => {
              const m = parseTime(e.target.value)
              if (m !== null) setTrip({ ...trip, endDeadline: m })
            }}
          />
        </div>

        <nav className="confirm__days" aria-label="여행 날짜">
          {trip.days.map((d, i) => {
            const n = needs(d.items)
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

          {day.items.map((it, index) => (
            <div className="confirm__card tp-fabric" key={it.id}>
              <div className="confirm__card-row">
                <img src={itemIcon(it)} alt="" aria-hidden="true" />
                <div className="confirm__card-text">
                  <span>
                    {hasTime(it) ? `${formatTime(it.start!)}–${formatTime(it.end!)}` : '시각 없음'} ·{' '}
                    {CATEGORY_LABEL[it.category]}
                    {it.reservationTime != null && ' · 예약'}
                  </span>
                  <b>{it.title}</b>
                </div>
              </div>
              {renderTime(it, index, day.items[index - 1])}
              {renderPlace(it)}
            </div>
          ))}
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
