import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router'
import { createRecovery, lockActivities, restoreActivity } from '../api/recoveries'
import type { Counterfactual, RecoveryInput, RecoveryResponse, RecoveryResult } from '../api/types'
import closedArt from '../assets/patches/hole-closed.svg'
import delayArt from '../assets/patches/hole-delay.svg'
import lateArt from '../assets/patches/hole-late.svg'
import rainArt from '../assets/patches/hole-rain.svg'
import tiredArt from '../assets/patches/hole-tired.svg'
import mendArt from '../assets/patches/patch-mend.svg'
import { CandidateCard } from '../components/CandidateCard'
import { SummaryBar } from '../components/SummaryBar'
import { WhyPanel } from '../components/WhyPanel'
import { StateCard } from '../components/StateCard'
import { StitchLoader } from '../components/StitchLoader'
import { useFlowTitle } from '../layout/flowTitle'
import { categoryIcon } from '../lib/category'
import { inputFor, samplePlan, titlesOf, type RecoveryState } from '../lib/recovery'
import { strategyLabel } from '../lib/strategy'
import { withJosa } from '../lib/josa'
import sample from '../mocks/scenarioAInput.json'
import './DiffView.css'

// The hole patch that shows what kind of thing broke the day.
const HOLE_ART: Record<string, string> = {
  DELAY: delayArt,
  WEATHER: rainArt,
  CLOSURE: closedArt,
  FATIGUE: tiredArt,
  EXTEND: lateArt,
}

// Headline when there are no chips (the page was opened directly): say what kind of hole it is.
const HOLE_TITLE: Record<string, string> = {
  DELAY: '출발이 늦어졌어요',
  WEATHER: '비 때문에 밖이 어려워요',
  CLOSURE: '가려던 곳이 문을 닫았어요',
  FATIGUE: '많이 걷기 힘들어요',
  EXTEND: '더 머물고 싶어요',
}

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
  const [attempt, setAttempt] = useState(0)
  const [notice, setNotice] = useState<string | null>(null)
  useFlowTitle(
    '패치 고르기',
    state.status === 'done' && state.response.candidates.length > 0
      ? `후보 ${state.response.candidates.length}개`
      : undefined,
  )

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
  }, [event, attempt])

  if (state.status === 'loading') {
    return (
      <StitchLoader
        steps={['구멍 크기를 재고 있어요', '덧댈 조각을 고르고 있어요', '원래 계획을 최대한 살리는 중이에요', '실을 꿰고 있어요']}
      />
    )
  }
  if (state.status === 'error') {
    return (
      <StateCard
        kind="error"
        title="패치를 찾다가 실이 엉켰어요"
        actions={
          <>
            <button
              type="button"
              className="tp-btn-primary tp-denim"
              onClick={() => {
                setState({ status: 'loading' })
                setAttempt((n) => n + 1)
              }}
            >
              다시 시도
            </button>
            <Link className="tp-btn-quiet" to="/">
              원래 일정 그대로 두기
            </Link>
          </>
        }
      >
        <p>{navigator.onLine ? '서버가 잠시 답하지 않아요. 잠깐 뒤 다시 해 주세요.' : '인터넷이 끊겨서 계산할 수 없어요.'}</p>
        <p>원래 일정은 그대로 남아 있어요.</p>
      </StateCard>
    )
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
  const iconOf = new Map(currentInput.activities.map((a) => [a.id, categoryIcon(a.category)]))

  async function restore(activityId: string): Promise<Counterfactual | null> {
    const res = await restoreActivity({ input: currentInput, strategy: candidate.strategy, activity_id: activityId })
    return res.counterfactual ?? null
  }

  function adopt(cf: Counterfactual) {
    setAdopted((a) => ({ ...a, [candidate.strategy]: cf.result }))
    setNotice(`${withJosa(titleOf.get(cf.restored_id) ?? '그 조각', '을/를')} 살린 안으로 바꿨어요.`)
  }

  async function lock(activityId: string) {
    setBusy(true)
    setNotice(null)
    try {
      const res = await lockActivities({ input: currentInput, activity_ids: [activityId] })
      const name = titleOf.get(activityId) ?? '그 조각'
      if (res.candidates.length === 0) {
        setNotice(`${withJosa(name, '을/를')} 원래대로 두면 맞출 수 있는 일정이 없어요. 지금 안을 그대로 둘게요.`)
        return
      }
      // Stay on the same strategy if it still exists.
      const keep = res.candidates.findIndex((c) => c.strategy === candidate.strategy)
      setState({ status: 'done', response: res })
      setPicked(Math.max(0, keep))
      setAdopted({})
      setNotice(`${withJosa(name, '을/를')} 원래대로 고정하고 다시 맞췄어요.`)
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
          <img className="diff-view__hole-art" src={HOLE_ART[event.type] ?? mendArt} alt="" aria-hidden="true" />
          <span className="diff-view__hole-tag tp-tagstitch">풀린 실</span>
          <h1>{chips[0] ?? HOLE_TITLE[event.type] ?? '일정에 구멍이 났어요'}</h1>
          {chips.length > 1 && (
            <ul>
              {chips.slice(1).map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
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

        <SummaryBar result={result} />

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
            iconOf={iconOf}
            renderDetail={(change) => (
              <WhyPanel
                change={change}
                event={event}
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
            eventType: event.type,
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
