import { Link, useLocation, useNavigate } from 'react-router'
import type { RecoveryInput, RecoveryResult } from '../api/types'
import delayPatch from '../assets/patches/hole-delay.svg'
import { OP_LABEL } from '../components/DiffRow'
import { CATEGORY_ICON, DEFAULT_ICON } from '../lib/placeIcons'
import { strategyLabel } from '../lib/strategy'
import { formatTime } from '../lib/time'
import sample from '../mocks/scenarioAInput.json'
import './Stitched.css'

const activities = new Map((sample as unknown as RecoveryInput).activities.map((a) => [a.id, a]))

export default function Stitched() {
  const navigate = useNavigate()
  const navState = useLocation().state as { result?: RecoveryResult; titles?: Record<string, string> } | null
  const result = navState?.result
  const titles = navState?.titles ?? {}

  // Opened without a chosen patch (e.g. typed URL): nothing to show.
  if (!result) {
    return (
      <div className="stitched">
        <header className="stitched__head tp-pinked-bottom">박음질 완료</header>
        <div className="stitched__body">
          <p>박음질한 패치가 없어요.</p>
          <Link className="tp-btn-primary tp-denim" to="/">
            오늘 일정으로
          </Link>
        </div>
      </div>
    )
  }

  const dropped = result.changes.filter((c) => c.op === 'drop').length
  const changed = result.changes.filter((c) => c.op !== 'keep' && c.op !== 'drop').length
  const rows = result.changes
    .filter((c) => c.op !== 'drop' && c.after)
    .sort((a, b) => a.after!.start - b.after!.start)

  return (
    <div className="stitched">
      <header className="stitched__head tp-pinked-bottom">박음질 완료</header>

      <div className="stitched__body">
        <div className="stitched__hero">
          <img src={delayPatch} alt="" aria-hidden="true" />
          {/* Round down, same as everywhere else: a plan that changed something must not read 100%. */}
          <h1>
            원래 계획의 {Math.floor(result.preservation_rate * 100)}%를
            <br />
            지켰어요
          </h1>
          <p>‘{strategyLabel(result.strategy)}’ 패치로 오늘의 원단을 박음질했어요.</p>
        </div>

        <div className="stitched__stats">
          <div>
            <span>바뀐 조각</span>
            <b>{changed}개</b>
          </div>
          <div>
            <span>뺀 조각</span>
            <b>{dropped}개</b>
          </div>
        </div>

        <section className="stitched__day tp-fabric" aria-label="새 오늘 일정">
          <h2>새로 박음질한 오늘</h2>
          <ul>
            {rows.map((c) => {
              const a = activities.get(c.activity_id)
              const patched = c.op !== 'keep'
              return (
                <li key={c.activity_id} className={patched ? 'stitched__row--patched' : undefined}>
                  <span className="stitched__time">{formatTime(c.after!.start)}</span>
                  <img src={(a && CATEGORY_ICON[a.category]) ?? DEFAULT_ICON} alt="" aria-hidden="true" />
                  <span className="stitched__text">
                    <b>
                      {c.substitute_id
                        ? (titles[c.substitute_id] ?? '다른 곳')
                        : (titles[c.activity_id] ?? a?.title ?? c.activity_id)}
                    </b>
                    <span>
                      {patched && c.before ? `${formatTime(c.before.start)}에서 ${OP_LABEL[c.op]}` : '그대로'}
                    </span>
                  </span>
                  {patched && <span className="stitched__chip tp-tagstitch">패치</span>}
                </li>
              )
            })}
          </ul>
        </section>

        {/* Saving is not built yet (needs the save API, stage 6): say so rather than imply it. */}
        <p className="stitched__note">아직 저장되지는 않아요. 저장 기능은 곧 연결할게요.</p>
      </div>

      <div className="stitched__bar tp-pinked-top">
        <button type="button" className="stitched__undo" onClick={() => navigate(-1)}>
          실 풀기
        </button>
        <Link className="tp-btn-primary tp-denim" to="/">
          오늘 일정으로
        </Link>
      </div>
    </div>
  )
}
