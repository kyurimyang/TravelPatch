import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { buildDisruption, interpretDisruption } from '../api/disruptions'
import { accessMessage, ApiError } from '../api/http'
import { addPlace, buildPlan } from '../api/plans'
import type { BuiltPlan, DisruptionEvent, EventDraft, InterpretResponse, PlaceOption, TravelTime, Wish } from '../api/types'
import { EventChips } from '../components/EventChips'
import addArt from '../assets/patches/place-sight.svg'
import { PlaceSearch } from '../components/PlaceSearch'
import closed from '../assets/patches/hole-closed.svg'
import delay from '../assets/patches/hole-delay.svg'
import late from '../assets/patches/hole-late.svg'
import rain from '../assets/patches/hole-rain.svg'
import tired from '../assets/patches/hole-tired.svg'
import { StitchLoader } from '../components/StitchLoader'
import {
  defaultVisited,
  HOTEL_ID,
  holeEvent,
  holeLocation,
  MAX_MORE_EVENTS,
  whereNow,
  nextActivity,
  planRequestFor,
  START_ID,
  samplePlan,
  visitLocked,
  type RecoveryState,
  type RecoverySource,
} from '../lib/recovery'
import { formatTime, parseTime } from '../lib/time'
import { deviceNow } from '../lib/today'
import { markFlowStart } from '../lib/nav'
import { ExitLink } from '../components/ExitLink'
import { closable, minutesLabel, ok, QUICK_ASK, quickResponse, type QuickKind } from '../lib/quick'
import { useTrip } from '../store/trip'
import './Recover.css'

// Quick buttons build the event by rules, after at most one choice (lib/quick.ts): no LLM call.
// A typed sentence goes through the interpret call as before.
const QUICK: { id: QuickKind; label: string; icon: string }[] = [
  { id: 'delay', label: '열차·버스 지연', icon: delay },
  { id: 'closed', label: '휴무·영업 종료', icon: closed },
  { id: 'rain', label: '비·날씨', icon: rain },
  { id: 'late', label: '출발이 늦어졌어요', icon: late },
  { id: 'tired', label: '지쳤어요 · 쉬고 싶어요', icon: tired },
  { id: 'add', label: '꼭 가고 싶은 곳 추가', icon: addArt },
]

type Phase =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'result'; response: InterpretResponse }

// The day being recovered: being built by the server, ready, or not possible (with why).
type DayState =
  | { kind: 'building' }
  | { kind: 'ready'; plan: BuiltPlan; source: RecoverySource }
  | { kind: 'blocked'; message: string }

const hasStart = (plan: BuiltPlan) => plan.day.start_lat != null

const WARNING_TEXT: Record<string, string> = {
  CLOSED_THAT_DAY: '이날은 쉬는 날로 나와요. 그대로 둘지 확인해 주세요.',
  BEFORE_ARRIVAL: '도착 후 공항에서 가기엔 시작이 너무 일러요.',
  AFTER_DEPARTURE: '출국 시각에 맞추기엔 너무 늦게 끝나요.',
}

/** Default "now": the phone's clock on the day being travelled; on an arrival day, when the
 * user can leave the airport; else 30 minutes before the first item. */
function defaultNow(plan: BuiltPlan): number {
  const d = new Date()
  if (plan.day.date === deviceNow().date) return d.getHours() * 60 + d.getMinutes()
  if (hasStart(plan)) return plan.day.start_time
  const first = Math.min(...plan.activities.map((a) => a.planned_start))
  return Math.max(0, Math.floor((first - 30) / 5) * 5)
}

export default function Recover() {
  const navigate = useNavigate()
  const { trip } = useTrip()
  // `hole`: the id of the piece the hole alert said is late (A2).
  useEffect(() => markFlowStart('recover'), [])
  // `sample`: opened from the intro's "try the example" (no trip needed).
  const navIn = useLocation().state as { dayIndex?: number; hole?: string; sample?: boolean } | null
  // Opened without a day (typed URL, or sent back here from a screen that lost its state):
  // the day being travelled, not always the first day of the trip.
  const todayIndex = trip ? trip.days.findIndex((d) => d.date === deviceNow().date) : -1
  const dayIndex = navIn?.dayIndex ?? Math.max(0, todayIndex)
  const hole = navIn?.hole ?? null

  // Why the trip day cannot be sent yet (derived, not stored): no trip, or unconfirmed items.
  const req = useMemo(() => (trip ? planRequestFor(trip, dayIndex) : null), [trip, dayIndex])
  const notReady = !req ? '등록한 여행이 없어요.' : 'problem' in req ? req.problem : null
  const [fetched, setFetched] = useState<DayState | null>(null)
  const [useSample, setUseSample] = useState(navIn?.sample === true)
  const [now, setNow] = useState<number | null>(null)
  // null = not chosen yet: the day's start (airport on an arrival day, else the hotel).
  const [locationId, setLocationId] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [quick, setQuick] = useState<QuickKind | null>(null)
  // "꼭 가고 싶은 곳": the picked place, then the server's travel table with it (MUST_VISIT).
  const [addPick, setAddPick] = useState<{ option: PlaceOption; title: string } | null>(null)
  const [added, setAdded] = useState<{ placeId: string; travel: TravelTime[] } | null>(null)
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })
  // A chip being fixed or a question being answered: the rules run again on the server.
  const [rebuilding, setRebuilding] = useState(false)
  // Already visited, left out of the recovery (A1): the user's taps over the pre-checked default.
  // Cleared whenever the event changes, so the default follows the new event.
  const [visitEdits, setVisitEdits] = useState<Record<string, boolean>>({})
  // Pieces Google says are closed that day go into the patch as closures (2026-11-27), unless the
  // user says they go anyway (Google's hours can be wrong; the user is the one standing there).
  const [goAnyway, setGoAnyway] = useState<Record<string, boolean>>({})

  // Build the trip day once on the server (coordinates + hours from Google, kept in memory only).
  useEffect(() => {
    if (!req || 'problem' in req) return
    let cancelled = false
    buildPlan(req)
      .then((plan) => !cancelled && setFetched({ kind: 'ready', plan, source: 'trip' }))
      .catch((e: Error) => {
        if (cancelled) return
        const message =
          accessMessage(e) ??
          (e instanceof ApiError && e.status === 503
            ? '장소 정보를 불러올 수 없어요. 서버에 장소 검색 키가 설정되어 있는지 확인해 주세요.'
            : '장소 정보를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.')
        setFetched({ kind: 'blocked', message })
      })
    return () => {
      cancelled = true
    }
  }, [req])

  const day: DayState = useSample
    ? { kind: 'ready', plan: samplePlan(), source: 'sample' }
    : notReady
      ? { kind: 'blocked', message: notReady }
      : (fetched ?? { kind: 'building' })

  if (day.kind !== 'ready') {
    return (
      <div className="recover">
        <div className="recover__body">
          <div className="recover__intro">
            <h1>
              원단 어디에
              <br />
              구멍이 났나요?
            </h1>
          </div>
          {day.kind === 'building' ? (
            <StitchLoader steps={['이날 원단을 펼치고 있어요', '장소와 영업시간을 확인하고 있어요', '이동 시간을 재고 있어요']} />
          ) : (
            <section className="recover__blocked tp-fabric">
              <p>{day.message}</p>
              {trip && (
                <Link className="tp-btn-quiet" to={`/trips/${trip.id}/edit`} state={{ dayIndex }}>
                  일정 확인으로 가기
                </Link>
              )}
              <button
                type="button"
                className="tp-btn-primary tp-denim"
                onClick={() => setUseSample(true)}
              >
                예시 여행(도쿄)으로 해 보기
              </button>
            </section>
          )}
        </div>
      </div>
    )
  }

  const { plan, source } = day
  const activities = plan.activities
  const nowMin = now ?? defaultNow(plan)
  const where =
    locationId ?? (hole ? holeLocation(plan, hole) : whereNow(plan, nowMin))
  const departureDay =
    source === 'trip' && !!trip?.departure && trip.days[dayIndex]?.date === trip.endDate
  const next = nextActivity(activities, nowMin)
  const titleOf = (id: string) => activities.find((a) => a.id === id)?.title ?? id

  async function understand() {
    setPhase({ kind: 'loading' })
    try {
      // No GPS in MVP (2026-11-17): the user says where they are.
      const response = await interpretDisruption({
        text: text.trim(),
        now: nowMin,
        location_id: where,
        activities,
      })
      setVisitEdits({})
      setPhase({ kind: 'result', response })
    } catch (e) {
      const message =
        accessMessage(e) ??
        (e instanceof ApiError && e.status === 503
          ? '지금은 한 줄 해석을 쓸 수 없어요. 서버에 AI 키가 설정되어 있는지 확인해 주세요.'
          : '해석하지 못했어요. 잠시 뒤 다시 시도해 주세요.')
      setPhase({ kind: 'error', message })
    }
  }

  // Fixed chip, answered question, taken-out event: the drafts go back through the same rules
  // (POST /disruptions/build, no LLM). Nothing left: back to an empty answer.
  async function rebuild(drafts: EventDraft[], wishes: Wish[]) {
    if (drafts.length === 0 && wishes.length === 0) {
      reset()
      return
    }
    setRebuilding(true)
    try {
      const response = await buildDisruption({ drafts, wishes, now: nowMin, location_id: where, activities })
      setVisitEdits({})
      setPhase({ kind: 'result', response })
    } catch (e) {
      setPhase({ kind: 'error', message: accessMessage(e) ?? '고친 내용을 반영하지 못했어요. 잠시 뒤 다시 시도해 주세요.' })
    } finally {
      setRebuilding(false)
    }
  }

  // From the hole alert, with nothing typed: the event is known without the LLM (A2). Typing a
  // sentence ("30분 더 걸려요") takes the usual interpret path instead.
  const fromHole: InterpretResponse | null =
    hole && phase.kind === 'idle' && text.trim() === ''
      ? ok(holeEvent(nowMin, where), [`${formatTime(nowMin)}부터 움직일 수 있어요`])
      : null
  const response = phase.kind === 'result' ? phase.response : fromHole
  const ready = response?.status === 'ok' && response.event != null
  // A typed sentence comes back as editable items; quick buttons and the hole alert as plain chips.
  const editable = !!response && (response.items.length > 0 || response.wish_chips.length > 0)
  const reset = () => {
    setAdded(null)
    setPhase({ kind: 'idle' })
    setVisitEdits({})
  }
  // Only what was planned to start before now can have been visited; the rest is not asked.
  const event = ready ? response.event! : null
  const moreEvents = ready ? response.events.slice(1) : []
  const locked = event ? visitLocked(event, moreEvents) : new Set<string>()
  const preChecked = new Set(event ? defaultVisited(plan, event, moreEvents) : [])
  const isVisited = (id: string) => !locked.has(id) && (visitEdits[id] ?? preChecked.has(id))
  const visitable = event
    ? activities.filter((a) => a.planned_start < event.occurred_at && !locked.has(a.id))
    : []
  const toggleVisited = (id: string) => setVisitEdits((e) => ({ ...e, [id]: !isVisited(id) }))
  // Closed that day, still ahead, not what an event is already about, not where the user stands.
  const closedToday = plan.warnings.filter((w) => w.code === 'CLOSED_THAT_DAY').map((w) => w.activity_id)
  const autoClosures: DisruptionEvent[] = event
    ? closedToday
        .filter((id) => !goAnyway[id] && !isVisited(id) && !locked.has(id) && id !== event.location_id)
        .slice(0, Math.max(0, MAX_MORE_EVENTS - moreEvents.length))
        .map((id) => ({ type: 'CLOSURE', occurred_at: event.occurred_at, location_id: event.location_id, activity_id: id }))
    : []

  return (
    <div className="recover">
      <div className="recover__body">
        <div className="recover__meta">
          {source === 'sample' ? '예시 여행 · 도쿄' : `DAY ${dayIndex + 1}`} · {formatTime(nowMin)}
        </div>
        <div className="recover__intro">
          <h1>
            원단 어디에
            <br />
            구멍이 났나요?
          </h1>
          <p>고르거나 한 줄로 적어 주시면, 영향 받는 조각을 찾아 볼게요.</p>
        </div>

        {plan.warnings.length > 0 && (
          <section className="recover__warn" role="note">
            {plan.warnings.map((w) =>
              w.code === 'CLOSED_THAT_DAY' ? (
                <p key={`${w.code}-${w.activity_id}`} className="recover__warn-row">
                  <span>
                    {titleOf(w.activity_id)}:{' '}
                    {goAnyway[w.activity_id]
                      ? '쉬는 날로 나오지만 그대로 갈게요.'
                      : '이날은 쉬는 날로 나와요. 패치에서 빼거나 근처로 바꿔요.'}
                  </span>
                  <button
                    type="button"
                    onClick={() => setGoAnyway((g) => ({ ...g, [w.activity_id]: !g[w.activity_id] }))}
                  >
                    {goAnyway[w.activity_id] ? '쉬는 날로 두기' : '그래도 갈게요'}
                  </button>
                </p>
              ) : (
                <p key={`${w.code}-${w.activity_id}`}>
                  {titleOf(w.activity_id)}: {WARNING_TEXT[w.code] ?? '확인이 필요해요.'}
                </p>
              ),
            )}
          </section>
        )}

        <fieldset className="recover__where tp-fabric">
          <legend>지금</legend>
          <label>
            <span>시각</span>
            <input
              type="time"
              step={300}
              value={formatTime(nowMin)}
              onChange={(e) => {
                const m = parseTime(e.target.value)
                if (m !== null) setNow(m)
                reset()
              }}
            />
          </label>
          <label>
            <span>있는 곳</span>
            <select
              value={where}
              onChange={(e) => {
                setLocationId(e.target.value)
                reset()
              }}
            >
              {hasStart(plan) && <option value={START_ID}>도착 공항</option>}
              {/* On a departure day the backend puts the airport in the hotel node (the day's end). */}
              <option value={HOTEL_ID}>{departureDay ? '출발 공항' : '숙소'}</option>
              {activities.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.title}
                </option>
              ))}
            </select>
          </label>
        </fieldset>

        {next && (
          <section className="recover__next tp-fabric" aria-label="지금 걸려 있는 조각">
            <span>
              <span>다음 조각</span>
              <b>
                {formatTime(next.planned_start)} {next.title}
              </b>
            </span>
          </section>
        )}

        <fieldset className="recover__quick">
          <legend>빠르게 고르기</legend>
          <div className="recover__quick-grid">
            {QUICK.map((q) => (
              <button
                key={q.id}
                type="button"
                aria-pressed={quick === q.id}
                className={q.id === 'tired' || q.id === 'add' ? 'recover__quick-wide' : undefined}
                onClick={() => {
                  setQuick(q.id)
                  setText('')
                  setVisitEdits({})
                  setAdded(null)
                  setAddPick(null)
                  // Nothing to choose (tired): the event is ready at once.
                  setPhase(
                    QUICK_ASK[q.id] === null
                      ? { kind: 'result', response: quickResponse(q.id, null, nowMin, where, titleOf) }
                      : { kind: 'idle' },
                  )
                }}
              >
                <img src={q.icon} alt="" aria-hidden="true" />
                {q.label}
              </button>
            ))}
          </div>
          {quick === 'add' && (
            <div className="recover__ask" role="group" aria-label="꼭 가고 싶은 곳">
              <span>어디를 넣을까요?</span>
              <PlaceSearch
                inputId="recover-add"
                city={source === 'sample' ? '도쿄' : (trip?.city ?? '')}
                placeholder="예: 팀랩 플래닛"
                picked={addPick?.option ?? null}
                onPick={(option, title) => {
                  setAddPick({ option, title })
                  setPhase({ kind: 'idle' })
                }}
              />
              {addPick && (
                <>
                  <span>얼마나 머물까요?</span>
                  <div className="recover__ask-options">
                    {(QUICK_ASK.add as { options: number[] }).options.map((m) => (
                      <button
                        key={m}
                        type="button"
                        disabled={phase.kind === 'loading'}
                        onClick={async () => {
                          setVisitEdits({})
                          setPhase({ kind: 'loading' })
                          try {
                            const res = await addPlace({
                              plan,
                              place_id: addPick.option.place_id,
                              title: addPick.title,
                              category: 'sightseeing',
                              duration: m,
                              now: nowMin,
                              location_id: where,
                            })
                            if (!res.event) {
                              setPhase({ kind: 'error', message: `${addPick.title}은(는) 이날 문을 닫는 곳으로 나와요.` })
                              return
                            }
                            setAdded({ placeId: addPick.option.place_id, travel: res.travel })
                            const unknown = res.hours === 'unknown' ? ' · 영업시간 확인 필요' : ''
                            setPhase({
                              kind: 'result',
                              response: ok(res.event, [`${addPick.title} · ${minutesLabel(m)} 넣기${unknown}`]),
                            })
                          } catch (e) {
                            setPhase({ kind: 'error', message: accessMessage(e) ?? '장소 정보를 불러오지 못했어요. 잠시 뒤 다시 해 주세요.' })
                          }
                        }}
                      >
                        {minutesLabel(m)}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
          {quick && quick !== 'add' && QUICK_ASK[quick] && (
            <div className="recover__ask" role="group" aria-label={QUICK_ASK[quick]!.label}>
              <span>{QUICK_ASK[quick]!.label}</span>
              <div className="recover__ask-options">
                {QUICK_ASK[quick]!.kind === 'place'
                  ? closable(plan, nowMin).map((a) => (
                      <button
                        key={a.id}
                        type="button"
                        onClick={() => {
                          setVisitEdits({})
                          setPhase({ kind: 'result', response: quickResponse(quick, a.id, nowMin, where, titleOf) })
                        }}
                      >
                        {formatTime(a.planned_start)} {a.title}
                      </button>
                    ))
                  : (QUICK_ASK[quick] as { options: number[] }).options.map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => {
                          setVisitEdits({})
                          setPhase({ kind: 'result', response: quickResponse(quick, m, nowMin, where, titleOf) })
                        }}
                      >
                        {QUICK_ASK[quick]!.kind === 'from' && m > 0 ? `${minutesLabel(m)} 뒤` : minutesLabel(m)}
                      </button>
                    ))}
              </div>
            </div>
          )}
        </fieldset>

        <div className="recover__field">
          <label htmlFor="situation">한 줄로 알려 주세요</label>
          <input
            id="situation"
            type="text"
            maxLength={500}
            placeholder="예: 비가 많이 와서 걷기 힘들어요"
            value={text}
            onChange={(e) => {
              setText(e.target.value)
              setQuick(null)
              setPhase({ kind: 'idle' })
            }}
          />
        </div>

        {phase.kind === 'loading' && <StitchLoader size="inline" steps={['한 줄을 읽고 있어요', '무슨 일인지 정리하고 있어요']} />}

        {phase.kind === 'error' && (
          <p className="recover__error" role="alert">
            {phase.message}
          </p>
        )}

        {response && (
          <section className="recover__chips tp-fabric" aria-label="이렇게 이해했어요" aria-live="polite">
            <h2>이렇게 이해했어요</h2>
            {editable && (
              <EventChips
                response={response}
                activities={activities}
                now={nowMin}
                busy={rebuilding}
                onChange={rebuild}
                onAddPlace={() => {
                  setText('')
                  setQuick('add')
                  setPhase({ kind: 'idle' })
                }}
              />
            )}
            {ready ? (
              <>
                {!editable && (
                  <ul>
                    {response.chips.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                )}
                <span className="recover__hint">
                  {fromHole
                    ? '더 늦어질 것 같다면 한 줄로 적어 주세요. 예: 20분 더 걸려요'
                    : quick
                      ? '다른 상황이면 버튼을 다시 고르거나 한 줄로 적어 주세요.'
                      : '칩마다 고치거나 뺄 수 있어요. 빠진 게 있으면 문장을 고쳐 다시 확인해 주세요.'}
                </span>
                {visitable.length > 0 && (
                  <fieldset className="recover__visited">
                    <legend>이미 다녀온 곳</legend>
                    <span className="recover__hint">체크한 곳은 그대로 두고, 남은 일정만 고쳐요.</span>
                    {visitable.map((a) => (
                      <label key={a.id}>
                        <input
                          type="checkbox"
                          checked={isVisited(a.id)}
                          onChange={() => toggleVisited(a.id)}
                        />
                        <span>
                          {formatTime(a.planned_start)} {a.title}
                        </span>
                        <em>{isVisited(a.id) ? '다녀왔어요' : '아직이에요'}</em>
                      </label>
                    ))}
                  </fieldset>
                )}
              </>
            ) : (
              <span className="recover__hint">
                {editable && response.events.length > 0
                  ? '이해한 건 위에 두었어요. 빠진 것만 골라 주세요.'
                  : editable
                    ? '어떤 일인지 위에서 골라 주세요.'
                    : '내용을 이해하지 못했어요. 조금 더 구체적으로 적어 주세요.'}
              </span>
            )}
          </section>
        )}

        <p className="recover__note">패치를 박음질하기 전까지 원래 일정은 그대로 남아 있어요.</p>
      </div>

      <div className="recover__bar tp-pinked-top">
        {ready ? (
          <button
            type="button"
            className="tp-btn-primary tp-denim"
            onClick={() => {
              // The whole day goes on; the server takes the ticked places out (2026-11-22).
              const state: RecoveryState = {
                // An added place brings its travel times with it (POST /plans/add-place).
                plan: added ? { ...plan, travel: added.travel } : plan,
                source,
                addedPlaceId: added?.placeId,
                event: response!.event!,
                moreEvents: [...moreEvents, ...autoClosures],
                wishes: response!.wishes,
                chips: [
                  ...response!.chips,
                  ...autoClosures.map((c) => `${titleOf('activity_id' in c ? c.activity_id : '')} · 오늘 쉬는 날`),
                ],
                visited: activities.filter((a) => isVisited(a.id)).map((a) => a.id),
              }
              navigate('/recover/patch', { state })
            }}
          >
            패치 찾아보기
          </button>
        ) : (
          <button
            type="button"
            className="tp-btn-primary tp-denim"
            disabled={text.trim() === '' || phase.kind === 'loading'}
            onClick={understand}
          >
            {phase.kind === 'loading' ? '읽는 중…' : '이렇게 이해했는지 확인'}
          </button>
        )}
        <ExitLink flow="recover" className="tp-btn-quiet">
          그대로 둘게요
        </ExitLink>
      </div>
    </div>
  )
}
