import { useState } from 'react'
import type { Counterfactual, DisruptionEvent, RecoveryChange } from '../api/types'
import { canLock, describeReason, NO_SINGLE_REASON } from '../lib/reasons'
import { OP_LABEL } from './DiffRow'
import { StitchLoader } from './StitchLoader'
import './WhyPanel.css'

type Props = {
  change: RecoveryChange
  /** The confirmed event: a delay's reason names when the user can move again. */
  event?: DisruptionEvent
  titleOf: ReadonlyMap<string, string>
  /** Absent when the plan on screen cannot be recomputed (e.g. an adopted "what if"). */
  onRestore?: (activityId: string) => Promise<Counterfactual | null>
  onAdopt?: (cf: Counterfactual) => void
  onLock?: (activityId: string) => void
  busy?: boolean
}

type Restore =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'done'; cf: Counterfactual | null }

const pct = (x: number) => Math.floor(x * 100)

// The "왜?" content of one changed row: the reason, then what the user can do about it.
export function WhyPanel({ change, event, titleOf, onRestore, onAdopt, onLock, busy }: Props) {
  const [restore, setRestore] = useState<Restore>({ kind: 'idle' })
  const reason = describeReason(change, event) ?? NO_SINGLE_REASON
  const title = (id: string) => titleOf.get(id) ?? id

  async function tryRestore() {
    if (!onRestore) return
    setRestore({ kind: 'loading' })
    try {
      setRestore({ kind: 'done', cf: await onRestore(change.activity_id) })
    } catch {
      setRestore({ kind: 'error' })
    }
  }

  return (
    <div className="why">
      <p className="why__reason">{reason}</p>

      {change.op === 'drop' && onRestore && restore.kind === 'idle' && (
        <button type="button" className="why__action" onClick={tryRestore} disabled={busy}>
          되살리면 어떻게 되나요?
        </button>
      )}
      {restore.kind === 'loading' && <StitchLoader size="inline" steps={['살려서 다시 맞춰 보고 있어요']} />}
      {restore.kind === 'error' && <p className="why__note">계산하지 못했어요. 잠시 뒤 다시 해 주세요.</p>}
      {restore.kind === 'done' && restore.cf === null && (
        <p className="why__note">이 조각을 살리면서 지킬 수 있는 일정이 없어요. 위 이유 때문에 빼야 해요.</p>
      )}
      {restore.kind === 'done' && restore.cf && (
        <div className="why__cf">
          <p>
            살리면 보존율이 <b>{pct(restore.cf.result.preservation_rate)}%</b>가 돼요 (
            {restore.cf.d_preservation >= 0 ? '+' : ''}
            {Math.round(restore.cf.d_preservation * 100)}%p).
          </p>
          {restore.cf.side_effects.length > 0 ? (
            <>
              <p>대신 이렇게 바뀌어요.</p>
              <ul>
                {restore.cf.side_effects.map((s) => (
                  <li key={s.activity_id}>
                    {title(s.activity_id)}: {OP_LABEL[s.before.op]} → <b>{OP_LABEL[s.after.op]}</b>
                    {s.after.op === 'shrink' && s.before.after && s.after.after && (
                      <>
                        {' '}
                        ({s.before.after.end - s.before.after.start}분 →{' '}
                        {s.after.after.end - s.after.after.start}분)
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p>다른 조각은 그대로예요.</p>
          )}
          {onAdopt && (
            <button type="button" className="why__action" onClick={() => onAdopt(restore.cf!)} disabled={busy}>
              이 안으로 바꾸기
            </button>
          )}
        </div>
      )}

      {/* Hidden where the original slot breaks a rule of its own: locking would always fail (A4). */}
      {canLock(change) && onLock && (
        <button type="button" className="why__action why__action--quiet" onClick={() => onLock(change.activity_id)} disabled={busy}>
          이건 원래대로 둘래요 (고정)
        </button>
      )}
    </div>
  )
}
