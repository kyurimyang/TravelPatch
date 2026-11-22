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

// Search result for one item. Missing from the map = still searching. unwritten = the text names
// no place for it: nothing is searched (never the title, decision 2026-11-23), the user picks.
type Match = { status: 'ok'; options: PlaceOption[] } | { status: 'error' } | { status: 'unwritten' }

export default function Confirm() {
  const { trip, setTrip, updateItem, updateTrip } = useTrip()
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
      if (it.placeId) continue
      if (it.placeFrom) {
        // Same place as another item of the day: copy it once that one has a place.
        const from = day.items.find((x) => x.id === it.placeFrom!.id)
        if (from?.placeId) updateItem(it.id, { placeId: from.placeId })
        continue
      }
      if (!it.placeQuery || requested.current.has(it.id)) continue // no query: see matchOf
      requested.current.add(it.id)
      searchPlaces(it.placeQuery, trip.city, trip.hotel?.placeId)
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

  // Flights read from the text (tripFromDraft): find their airport, then they are the trip's
  // flights like ones entered at registration. A take-off the text does not give is flagged.
  useEffect(() => {
    const pending = trip?.textFlights
    if (!trip || !pending) return
    for (const which of ['arrival', 'departure'] as const) {
      const f = pending[which]
      const key = `flight:${which}`
      if (!f?.airport_query || trip[which] || requested.current.has(key)) continue
      requested.current.add(key)
      const title = f.airport_query
      searchPlaces(title, trip.city, trip.hotel?.placeId)
        .then(({ candidates }) => {
          const first = candidates[0]
          if (!first) return
          updateTrip((t) => ({
            [which]: { time: f.time, airport: { title, placeId: first.place_id }, bufferMinutes: f.buffer_minutes },
            textFlights: t.textFlights && { ...t.textFlights, [which]: null },
            ...(which === 'departure' ? { departureTimeGuessed: !f.time_written } : {}),
          }))
        })
        .catch(() => {}) // the trip simply has no flight then, as before this step
    }
  }, [trip, updateTrip])

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
  const flightNeeds = trip.departure && trip.departureTimeGuessed ? 1 : 0
  const totalNeeds = trip.days.reduce((n, d) => n + needs(d.items), 0) + flightNeeds
  const otherNeeds = totalNeeds - needs(day.items) - flightNeeds
  function pick(item: TripItem, place: PlaceOption) {
    // The user chose it themselves: no "far from the hotel" second look. Picking for an item
    // that shared another's place makes it its own; items sharing this one's place follow it.
    const chosen = { ...place, far: null }
    const followers = day!.items.filter((x) => x.placeFrom?.id === item.id && x.placeId === item.placeId)
    setChoice((c) => ({ ...c, [item.id]: chosen, ...Object.fromEntries(followers.map((x) => [x.id, chosen])) }))
    updateItem(item.id, { placeId: place.place_id, placeFrom: null })
    for (const x of followers) updateItem(x.id, { placeId: place.place_id })
    setOpen(null)
  }

  // Why an item has another's place, in the user's words (shown under the place).
  function sharedLabel(it: TripItem): string | null {
    const from = it.placeFrom && day!.items.find((x) => x.id === it.placeFrom!.id)
    if (!from) return null
    return it.placeFrom!.why === 'venue'
      ? `“${from.title}” 안이라 같은 장소로 묶었어요`
      : `앞 일정 “${from.title}”의 장소를 이어 썼어요`
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

  // An item with nothing to search or copy is never searched: it waits for the user.
  function matchOf(it: TripItem): Match | undefined {
    if (matches[it.id]) return matches[it.id]
    return !it.placeId && !it.placeFrom && !it.placeQuery ? { status: 'unwritten' } : undefined
  }

  // Google's name to show: the item's own pick, or, while it still shares a place, the other's.
  function shownOf(it: TripItem): PlaceOption | undefined {
    if (choice[it.id]) return choice[it.id]
    const from = it.placeFrom && day!.items.find((x) => x.id === it.placeFrom!.id)
    const theirs = from && from.placeId === it.placeId ? choice[from.id] : undefined
    return theirs && { ...theirs, far: null }
  }

  function renderPlace(it: TripItem) {
    const match = matchOf(it)
    const shown = shownOf(it)
    const options = match?.status === 'ok' ? match.options : []

    if (open === it.id || (!it.placeId && match)) {
      // Choosing: candidates (if any) + manual search.
      return (
        <div className="confirm__choose">
          {match?.status === 'error' && <p className="confirm__hint">검색하지 못했어요. 직접 찾아 주세요</p>}
          {match?.status === 'unwritten' && <p className="confirm__warn">장소가 적혀 있지 않아요. 찾아 주세요</p>}
          {match?.status === 'ok' && options.length === 0 && (
            <p className="confirm__hint">
              {withJosa(`“${it.placeQuery ?? it.title}”`, '으로/로')} 찾은 곳이 없어요. 직접 찾아 주세요
            </p>
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

    if (!it.placeId && it.placeFrom) {
      const from = day!.items.find((x) => x.id === it.placeFrom!.id)
      return <p className="confirm__hint">“{from?.title ?? '앞 일정'}”의 장소가 정해지면 같이 채워져요</p>
    }
    if (!match && !it.placeId) return <p className="confirm__hint">장소를 찾고 있어요…</p>

    const shared = sharedLabel(it)
    return (
      <>
        {shared && <p className="confirm__hint">{shared}</p>}
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

        {trip.departure && trip.departureTimeGuessed && (
          <div className="confirm__deadline tp-fabric">
            <label htmlFor="departure-time">
              <b>출국편 출발 시각</b>
              <span>적혀 있지 않아 탑승 대기가 끝나는 시각으로 뒀어요. 맞는지 봐 주세요</span>
            </label>
            <input
              id="departure-time"
              type="time"
              step={300}
              value={formatTime(trip.departure.time)}
              onChange={(e) => {
                const m = parseTime(e.target.value)
                const d = trip.departure!
                // The written fact is when the traveler is at the airport: keep it, move the buffer.
                const atAirport = d.time - (d.bufferMinutes ?? 0)
                if (m !== null && m > atAirport) {
                  updateTrip(() => ({
                    departure: { ...d, time: m, bufferMinutes: m - atAirport },
                    departureTimeGuessed: false,
                  }))
                }
              }}
            />
            <button type="button" className="confirm__link" onClick={() => updateTrip(() => ({ departureTimeGuessed: false }))}>
              맞아요
            </button>
          </div>
        )}

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
