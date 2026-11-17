import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router'
import { createRecovery, lockActivities, restoreActivity } from '../api/recoveries'
import type { Counterfactual, RecoveryInput, RecoveryResponse, RecoveryResult } from '../api/types'
import { CandidateCard } from '../components/CandidateCard'
import { WhyPanel } from '../components/WhyPanel'
import { StitchLoader } from '../components/StitchLoader'
import { inputFor, samplePlan, titlesOf, type RecoveryState } from '../lib/recovery'
import { strategyLabel } from '../lib/strategy'
import sample from '../mocks/scenarioAInput.json'
import './DiffView.css'

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'done'; response: RecoveryResponse }

export default function DiffView() {
  const nav = useLocation().state as RecoveryState | null
  // Opening this URL directly falls back to the sample day and its own event (scenario A).
  const plan = nav?.plan ?? samplePlan()
  const source = nav?.source ?? 'sample'
  const event = nav?.event ?? (sample as unknown as RecoveryInput).event
  const chips = nav?.chips ?? []
  const baseInput = inputFor(plan, event)

  const [state, setState] = useState<State>({ status: 'loading' })
  const [picked, setPicked] = useState(0)
  // A "what if I keep X" plan the user switched to, per strategy. Shown instead of the candidate;
  // it is final for that card (no further restore/lock on top of it).
  const [adopted, setAdopted] = useState<Record<string, RecoveryResult>>({})
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    // `cancelled` drops a stale answer if the effect re-runs (StrictMode runs it twice in dev).
    let cancelled = false
    createRecovery(baseInput)
      .then((response) => !cancelled && setState({ status: 'done', response }))
      .catch((e: Error) => !cancelled && setState({ status: 'error', message: e.message }))
    return () => {
      cancelled = true
    }
    // baseInput is derived from the navigation state, which only changes together with event.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [event])

  if (state.status === 'loading') {
    return (
      <StitchLoader
        steps={['구멍 크기를 재고 있어요', '덧댈 조각을 고르고 있어요', '원래 계획을 최대한 살리는 중이에요', '실을 꿰고 있어요']}
      />
    )
  }
  if (state.status === 'error') {
    return <div className="diff-view__msg">불러오지 못했어요: {state.message}</div>
  }

  const { candidates, blockers } = state.response
  // No plan at all: the blocker screen explains why.
  if (candidates.length === 0) {
    return (
      <Navigate
        to="/recover/blocked"
        replace
        state={{ blockers, chips, titles: Object.fromEntries(titlesOf(baseInput)) }}
      />
    )
  }

  const candidate = candidates[picked]
  const result = adopted[candidate.strategy] ?? candidate
  const isAdopted = result !== candidate
  // The input the server really used (with searched substitutes and earlier locks).
  const currentInput = state.response.used_input ?? baseInput
  const titleOf = titlesOf(currentInput)

  async function restore(activityId: string): Promise<Counterfactual | null> {
    const res = await restoreActivity({ input: currentInput, strategy: candidate.strategy, activity_id: activityId })
    return res.counterfactual ?? null
  }

  function adopt(cf: Counterfactual) {
    setAdopted((a) => ({ ...a, [candidate.strategy]: cf.result }))
    setNotice(`${titleOf.get(cf.restored_id) ?? '그 조각'}을(를) 살린 안으로 바꿨어요.`)
  }

  async function lock(activityId: string) {
    setBusy(true)
    setNotice(null)
    try {
      const res = await lockActivities({ input: currentInput, activity_ids: [activityId] })
      const name = titleOf.get(activityId) ?? '그 조각'
      if (res.candidates.length === 0) {
        setNotice(`${name}을(를) 원래대로 두면 맞출 수 있는 일정이 없어요. 지금 안을 그대로 둘게요.`)
        return
      }
      // Stay on the same strategy if it still exists.
      const keep = res.candidates.findIndex((c) => c.strategy === candidate.strategy)
      setState({ status: 'done', response: res })
      setPicked(Math.max(0, keep))
      setAdopted({})
      setNotice(`${name}을(를) 원래대로 고정하고 다시 맞췄어요.`)
    } catch {
      setNotice('다시 맞추지 못했어요. 잠시 뒤 다시 해 주세요.')
    } finally {
      setBusy(false)
    }
  }
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
          {busy && <StitchLoader size="inline" steps={['고정하고 다시 맞추는 중이에요']} />}
          {notice && (
            <p className="diff-view__notice" role="status">
              {notice}
            </p>
          )}
          <CandidateCard
            result={result}
            titleOf={titleOf}
            renderDetail={(change) => (
              <WhyPanel
                change={change}
                titleOf={titleOf}
                onRestore={isAdopted ? undefined : restore}
                onAdopt={isAdopted ? undefined : adopt}
                onLock={isAdopted ? undefined : lock}
                busy={busy}
              />
            )}
          />
        </section>

        <p className="diff-view__note">박음질 전까지 원래 일정은 그대로 남아 있어요.</p>
      </div>

      <div className="diff-view__bar tp-pinked-top">
        <Link
          className="tp-btn-primary tp-denim"
          to="/recover/done"
          state={{
            result,
            source,
            plan,
            chips,
            // Made once here, so a re-render or StrictMode re-run of Stitched cannot save twice.
            patchId: `${plan.day.date ?? 'day'}-${Date.now()}`,
            titles: Object.fromEntries(titleOf),
          }}
        >
          이 패치로 박음질하기
        </Link>
        <Link className="tp-btn-quiet" to="/">
          그대로 둘게요
        </Link>
      </div>
    </div>
  )
}
