import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { interpretDisruption } from '../api/disruptions'
import { ApiError } from '../api/http'
import type { InterpretResponse, RecoveryInput } from '../api/types'
import closed from '../assets/patches/hole-closed.svg'
import delay from '../assets/patches/hole-delay.svg'
import late from '../assets/patches/hole-late.svg'
import rain from '../assets/patches/hole-rain.svg'
import tired from '../assets/patches/hole-tired.svg'
import { formatTime } from '../lib/time'
import sample from '../mocks/scenarioAInput.json'
import './Recover.css'

// Same stand-in day as DiffView (scenario A) until the register API exists (stage 6).
const activities = (sample as unknown as RecoveryInput).activities
// Mock "now" (minutes since midnight). The server never reads a clock; the client sends it.
const NOW = 9 * 60

// Quick buttons only fill the sentence box; they go through the same interpret call as typed text.
const QUICK = [
  { id: 'delay', label: '열차·버스 지연', icon: delay, text: '열차가 한 시간쯤 늦게 와요' },
  { id: 'closed', label: '휴무·영업 종료', icon: closed, text: '이자카야가 임시휴무래요' },
  { id: 'rain', label: '비·날씨', icon: rain, text: '12시부터 비가 와요' },
  { id: 'late', label: '출발이 늦어졌어요', icon: late, text: '늦잠 자서 두 시간 뒤에 출발해요' },
  { id: 'tired', label: '지쳤어요 · 쉬고 싶어요', icon: tired, text: '일행이 지쳐서 많이 걷기 힘들어요' },
] as const

type Phase =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'result'; response: InterpretResponse }

export default function Recover() {
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [quick, setQuick] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })

  const next = activities.find((a) => a.planned_start >= NOW)
  const titleOf = (id: string) => activities.find((a) => a.id === id)?.title ?? id

  async function understand() {
    setPhase({ kind: 'loading' })
    try {
      // location_id "hotel" = where the user is. No GPS in MVP (2026-11-17): the user picks their place.
      const response = await interpretDisruption({
        text: text.trim(),
        now: NOW,
        location_id: 'hotel',
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

  return (
    <div className="recover">
      <div className="recover__body">
        <div className="recover__meta">DAY 1 · {formatTime(NOW)}</div>
        <div className="recover__intro">
          <h1>
            원단 어디에
            <br />
            구멍이 났나요?
          </h1>
          <p>고르거나 한 줄로 적어 주시면, 영향 받는 조각을 찾아 볼게요.</p>
        </div>

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
            onClick={() => navigate('/recover/patch', { state: { event: response!.event, chips: response!.chips } })}
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
