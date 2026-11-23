import { useLocation, useNavigate } from 'react-router'
import type { Blocker, Relaxation } from '../api/types'
import { BlockerList } from '../components/BlockerList'
import { ExitLink } from '../components/ExitLink'
import { backToFlowStart } from '../lib/nav'
import type { RecoveryState } from '../lib/recovery'
import './NoPatch.css'

type NoPatchState = {
  blockers?: Blocker[]
  relaxations?: Relaxation[]
  chips?: string[]
  titles?: Record<string, string>
  /** The request that found nothing, to ask again with one must loosened. */
  back?: RecoveryState
} | null

// "Relax a condition and retry": the server names the musts that, as "좋음", let a plan exist.
// Asking again goes through the normal patch screen, so what the user sees is a real candidate.
// "Tell me when things change" is still out (no live monitoring in the MVP).
export default function NoPatch() {
  const navigate = useNavigate()
  const { blockers = [], relaxations = [], chips = [], titles = {}, back } = (useLocation().state as NoPatchState) ?? {}
  const titleOf = new Map(Object.entries(titles))

  function retryWith(activityId: string) {
    if (!back) return
    const preferences = back.plan.preferences.map((p) => (p.activity_id === activityId ? { ...p, tier: 'nice' as const } : p))
    // replace: this screen stood in for the patch screen; back still leads to Recover.
    navigate('/recover/patch', { replace: true, state: { ...back, plan: { ...back.plan, preferences } } })
  }

  return (
    <div className="no-patch">
      <div className="no-patch__body">
        <h1 className="no-patch__title">패치를 찾지 못했어요</h1>

        <section className="no-patch__hole tp-fabric" aria-label="구멍 요약">
          <span className="no-patch__tag tp-tagstitch">풀린 실</span>
          {chips.length > 0 ? <b>{chips.join(' · ')}</b> : <b>이 사건으로는 일정을 맞출 수 없었어요</b>}
        </section>

        <div className="no-patch__blockers">
          <BlockerList blockers={blockers} titleOf={titleOf} />
        </div>

        {back && relaxations.length > 0 && (
          <section className="no-patch__relax" aria-label="이렇게 하면 패치가 있어요">
            <h2>이렇게 하면 패치가 있어요</h2>
            <ul>
              {relaxations.map((r) => {
                const title = titleOf.get(r.activity_id) ?? '이 조각'
                return (
                  <li key={r.activity_id}>
                    <span>
                      <span>
                        <b>‘{title}’</b>의 중요도를 꼭 → 좋음으로
                      </span>
                      <small>보존율 {Math.floor(r.preservation_rate * 100)}%</small>
                    </span>
                    <button type="button" className="no-patch__relax-btn" onClick={() => retryWith(r.activity_id)}>
                      이렇게 찾기
                    </button>
                  </li>
                )
              })}
            </ul>
            <p className="no-patch__relax-note">이번 패치에만 적용돼요. 여행 원단의 중요도는 그대로예요.</p>
          </section>
        )}

        <p className="no-patch__note">원래 일정은 그대로 남아 있어요.</p>
      </div>

      <div className="no-patch__bar tp-pinked-top">
        {/* Back to the Recover screen it came from (same day), not a new copy of it on top. */}
        <button type="button" className="tp-btn-primary tp-denim" onClick={() => backToFlowStart(navigate, 'recover', '/recover')}>
          상황 다시 입력하기
        </button>
        <ExitLink flow="recover" className="tp-btn-quiet">
          그대로 둘게요
        </ExitLink>
      </div>
    </div>
  )
}
