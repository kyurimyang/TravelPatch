import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { interpretDisruption } from '../api/disruptions'
import { ApiError } from '../api/http'
import { buildPlan } from '../api/plans'
import type { BuiltPlan, InterpretResponse } from '../api/types'
import closed from '../assets/patches/hole-closed.svg'
import delay from '../assets/patches/hole-delay.svg'
import late from '../assets/patches/hole-late.svg'
import rain from '../assets/patches/hole-rain.svg'
import tired from '../assets/patches/hole-tired.svg'
import { planRequestFor, samplePlan, type RecoveryState, type RecoverySource } from '../lib/recovery'
import { formatTime, parseTime } from '../lib/time'
import { useTrip } from '../store/trip'
import './Recover.css'

// Quick buttons only fill the sentence box; they go through the same interpret call as typed text.
const QUICK = [
  { id: 'delay', label: '열차·버스 지연', icon: delay, text: '열차가 한 시간쯤 늦게 와요' },
  { id: 'closed', label: '휴무·영업 종료', icon: closed, text: '저녁 먹을 곳이 임시휴무래요' },
  { id: 'rain', label: '비·날씨', icon: rain, text: '12시부터 비가 와요' },
  { id: 'late', label: '출발이 늦어졌어요', icon: late, text: '늦잠 자서 두 시간 뒤에 출발해요' },
  { id: 'tired', label: '지쳤어요 · 쉬고 싶어요', icon: tired, text: '일행이 지쳐서 많이 걷기 힘들어요' },
] as const

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

function deviceToday(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Default "now": the phone's clock on the day being travelled, else 30 minutes before the first item. */
function defaultNow(plan: BuiltPlan): number {
  const d = new Date()
  if (plan.day.date === deviceToday()) return d.getHours() * 60 + d.getMinutes()
  const first = Math.min(...plan.activities.map((a) => a.planned_start))
  return Math.max(0, Math.floor((first - 30) / 5) * 5)
}

export default function Recover() {
  const navigate = useNavigate()
  const { trip } = useTrip()
  const dayIndex = (useLocation().state as { dayIndex?: number } | null)?.dayIndex ?? 0

  // Why the trip day cannot be sent yet (derived, not stored): no trip, or unconfirmed items.
  const req = useMemo(() => (trip ? planRequestFor(trip, dayIndex) : null), [trip, dayIndex])
  const notReady = !req ? '등록한 여행이 없어요.' : 'problem' in req ? req.problem : null
  const [fetched, setFetched] = useState<DayState | null>(null)
  const [useSample, setUseSample] = useState(false)
  const [now, setNow] = useState<number | null>(null)
  const [locationId, setLocationId] = useState('hotel')
  const [text, setText] = useState('')
  const [quick, setQuick] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })

  // Build the trip day once on the server (coordinates + hours from Google, kept in memory only).
  useEffect(() => {
    if (!req || 'problem' in req) return
    let cancelled = false
    buildPlan(req)
      .then((plan) => !cancelled && setFetched({ kind: 'ready', plan, source: 'trip' }))
      .catch((e: Error) => {
        if (cancelled) return
        const message =
          e instanceof ApiError && e.status === 503
            ? '장소 정보를 불러올 수 없어요. 서버에 장소 검색 키가 설정되어 있는지 확인해 주세요.'
            : '장소 정보를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.'
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
            <p className="recover__note">이날 원단을 펼치고 있어요…</p>
          ) : (
            <section className="recover__blocked tp-fabric">
              <p>{day.message}</p>
              {trip && (
                <Link className="tp-btn-quiet" to="/new/confirm">
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
  const next = activities.find((a) => a.planned_start >= nowMin)
  const titleOf = (id: string) => activities.find((a) => a.id === id)?.title ?? id

  async function understand() {
    setPhase({ kind: 'loading' })
    try {
      // No GPS in MVP (2026-11-17): the user says where they are.
      const response = await interpretDisruption({
        text: text.trim(),
        now: nowMin,
        location_id: locationId,
        activities,
      })
      setPhase({ kind: 'result', response })
    } catch (e) {
      const message =
        e instanceof ApiError && e.status === 503
          ? '지금은 한 줄 해석을 쓸 수 없어요. 서버에 AI 키가 설정되어 있는지 확인해 주세요.'
          : '해석하지 못했어요. 잠시 뒤 다시 시도해 주세요.'
      setPhase({ kind: 'error', message })
    }
  }

  const response = phase.kind === 'result' ? phase.response : null
  const ready = response?.status === 'ok' && response.event !== null
  const reset = () => setPhase({ kind: 'idle' })

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
            {plan.warnings.map((w) => (
              <p key={w.activity_id}>{titleOf(w.activity_id)}: 이날은 쉬는 날로 나와요. 그대로 둘지 확인해 주세요.</p>
            ))}
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
              value={locationId}
              onChange={(e) => {
                setLocationId(e.target.value)
                reset()
              }}
            >
              <option value="hotel">숙소</option>
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
          <div>
            {QUICK.map((q) => (
              <button
                key={q.id}
                type="button"
                aria-pressed={quick === q.id}
                className={q.id === 'tired' ? 'recover__quick-wide' : undefined}
                onClick={() => {
                  setQuick(q.id)
                  setText(q.text)
                  setPhase({ kind: 'idle' })
                }}
              >
                <img src={q.icon} alt="" aria-hidden="true" />
                {q.label}
              </button>
            ))}
          </div>
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

        {phase.kind === 'error' && (
          <p className="recover__error" role="alert">
            {phase.message}
          </p>
        )}

        {response && (
          <section className="recover__chips tp-fabric" aria-label="이렇게 이해했어요" aria-live="polite">
            <h2>이렇게 이해했어요</h2>
            {ready ? (
              <>
                <ul>
                  {response.chips.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
                <span className="recover__hint">다르게 이해했다면 문장을 고쳐서 다시 확인해 주세요.</span>
              </>
            ) : (
              <>
                <p>{response.problem?.detail ?? '내용을 이해하지 못했어요. 조금 더 구체적으로 적어 주세요.'}</p>
                {!!response.problem?.candidates.length && (
                  <span className="recover__hint">
                    후보: {response.problem.candidates.map(titleOf).join(', ')} — 이름을 넣어 다시 적어 주세요.
                  </span>
                )}
              </>
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
              const state: RecoveryState = { plan, source, event: response!.event!, chips: response!.chips }
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
        <Link className="tp-btn-quiet" to="/">
          그대로 둘게요
        </Link>
      </div>
    </div>
  )
}
