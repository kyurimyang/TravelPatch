import { Link, useLocation } from 'react-router'
import type { Blocker, RecoveryInput } from '../api/types'
import { BlockerList } from '../components/BlockerList'
import sample from '../mocks/scenarioAInput.json'
import './NoPatch.css'

const titleOf = new Map((sample as unknown as RecoveryInput).activities.map((a) => [a.id, a.title]))

type NoPatchState = { blockers?: Blocker[]; chips?: string[] } | null

// The mockup also offers "relax a condition and retry" and "tell me when things change". Neither
// exists yet (no what-if API; live monitoring is out of the MVP), so they are left out on purpose.
export default function NoPatch() {
  const { blockers = [], chips = [] } = useLocation().state as NonNullable<NoPatchState> ?? {}

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

        <p className="no-patch__note">원래 일정은 그대로 남아 있어요.</p>
      </div>

      <div className="no-patch__bar tp-pinked-top">
        <Link className="tp-btn-primary tp-denim" to="/recover">
          상황 다시 입력하기
        </Link>
        <Link className="tp-btn-quiet" to="/">
          그대로 둘게요
        </Link>
      </div>
    </div>
  )
}
