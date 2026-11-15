import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router'
import { createRecovery } from '../api/recoveries'
import type { DisruptionEvent, RecoveryInput, RecoveryResponse } from '../api/types'
import { CandidateCard } from '../components/CandidateCard'
import { strategyLabel } from '../lib/strategy'
import sample from '../mocks/scenarioAInput.json'
import './DiffView.css'

// Sample input = scenario A (backend/tests/scenarios/scenario_a.json). Until the register screen
// exists, this is the day the app recovers.
const baseInput = sample as unknown as RecoveryInput
const titleOf = new Map(baseInput.activities.map((a) => [a.id, a.title]))

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'done'; response: RecoveryResponse }

// What Recover hands over: the event the user confirmed and the chips that said what was understood.
type RecoverState = { event?: DisruptionEvent; chips?: string[] } | null

export default function DiffView() {
  const nav = (useLocation().state as RecoverState) ?? {}
  // Opening this URL directly falls back to the sample's own event (scenario A).
  const event = nav.event ?? baseInput.event
  const chips = nav.chips ?? []

  const [state, setState] = useState<State>({ status: 'loading' })
  const [picked, setPicked] = useState(0)

  useEffect(() => {
    // `cancelled` drops a stale answer if the effect re-runs (StrictMode runs it twice in dev).
    let cancelled = false
    createRecovery({ ...baseInput, event })
      .then((response) => !cancelled && setState({ status: 'done', response }))
      .catch((e: Error) => !cancelled && setState({ status: 'error', message: e.message }))
    return () => {
      cancelled = true
    }
  }, [event])

  if (state.status === 'loading') return <div className="diff-view__msg">복구안을 계산하고 있어요…</div>
  if (state.status === 'error') {
    return <div className="diff-view__msg">불러오지 못했어요: {state.message}</div>
  }

  const { candidates, blockers } = state.response
  // No plan at all: the blocker screen explains why.
  if (candidates.length === 0) {
    return <Navigate to="/recover/blocked" replace state={{ blockers, chips }} />
  }

  const result = candidates[picked]
  const changed = result.changes.filter((c) => c.op !== 'keep').length

  return (
    <div className="diff-view">
      <div className="diff-view__body">
        <section className="diff-view__hole tp-fabric" aria-label="구멍 요약">
          <span className="diff-view__hole-tag tp-tagstitch">풀린 실</span>
          {chips.length > 0 ? (
            <ul>
              {chips.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          ) : (
            <p>이 사건으로 일정을 다시 맞췄어요</p>
          )}
          <div className="diff-view__stats">
            <div>
              <span>바뀌는 조각</span>
              <b>{changed}개</b>
            </div>
            <div>
              <span>그대로인 조각</span>
              <b>{result.changes.length - changed}개</b>
            </div>
          </div>
        </section>

        <div role="tablist" aria-label="패치 후보" className="diff-view__tabs">
          {candidates.map((c, i) => (
            <button
              key={c.strategy}
              type="button"
              role="tab"
              aria-selected={i === picked}
              className="tp-fabric"
              onClick={() => setPicked(i)}
            >
              <span>{strategyLabel(c.strategy)}</span>
              {/* Round down, same as SummaryBar: a plan that changed something must not read 100%. */}
              <span>보존율 {Math.floor(c.preservation_rate * 100)}%</span>
            </button>
          ))}
        </div>

        <section className="diff-view__preview" aria-label="선택한 패치 미리보기">
          <div className="diff-view__preview-head">
            <span>원래 일정과 달라지는 곳</span>
            <span className="tp-tagstitch">시침질 중</span>
          </div>
          <CandidateCard result={result} titleOf={titleOf} />
        </section>

        <p className="diff-view__note">박음질 전까지 원래 일정은 그대로 남아 있어요.</p>
      </div>

      <div className="diff-view__bar tp-pinked-top">
        <Link className="tp-btn-primary tp-denim" to="/recover/done" state={{ result }}>
          이 패치로 박음질하기
        </Link>
        <Link className="tp-btn-quiet" to="/">
          그대로 둘게요
        </Link>
      </div>
    </div>
  )
}
