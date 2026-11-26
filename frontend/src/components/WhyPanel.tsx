import { useState } from 'react'
import type { Counterfactual, RecoveryChange } from '../api/types'
import { canLock } from '../lib/reasons'
import { tradeoffs } from '../lib/tradeoff'
import './WhyPanel.css'

type Props = {
  change: RecoveryChange
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

// What the user can do about one changed row, right under it (2026-11-27). No fold to open and no
// paragraph to read: "살리기" on a dropped piece shows in one line what that costs ("대신 시부야
// 쇼핑 −40분"), then one tap to take it. "원래대로" where locking can work.
export function WhyPanel({ change, titleOf, onRestore, onAdopt, onLock, busy }: Props) {
  const [restore, setRestore] = useState<Restore>({ kind: 'idle' })
  const title = (id: string) => titleOf.get(id) ?? '다른 곳'
  const restorable = change.op === 'drop' && !!onRestore
  const lockable = canLock(change) && !!onLock
  if (!restorable && !lockable) return null

  async function tryRestore() {
    if (!onRestore) return
    setRestore({ kind: 'loading' })
    try {
      setRestore({ kind: 'done', cf: await onRestore(change.activity_id) })
    } catch {
      setRestore({ kind: 'error' })
    }
  }

  if (restore.kind === 'done' && restore.cf) {
    const cf = restore.cf
    const lost = tradeoffs(cf, title)
    return (
      <div className="why why--open" role="group" aria-label="살리면">
        <p className="why__cost">
          {lost.length === 0 ? (
            '살려도 다른 조각은 그대로예요'
          ) : (
            <>
              <span>대신</span>
              {lost.map((l) => (
                <span key={l} className="why__loss">
                  {l}
                </span>
              ))}
            </>
          )}
        </p>
        <span className="why__buttons">
          {onAdopt && (
            <button type="button" className="why__action" onClick={() => onAdopt(cf)} disabled={busy}>
              이렇게 살리기
            </button>
          )}
          <button type="button" className="why__link" onClick={() => setRestore({ kind: 'idle' })}>
            그만두기
          </button>
        </span>
      </div>
    )
  }

  return (
    <div className="why">
      {restorable && (
        <button type="button" className="why__link" onClick={tryRestore} disabled={busy || restore.kind === 'loading'}>
          {restore.kind === 'loading' ? '맞춰 보는 중…' : '살리기'}
        </button>
      )}
      {lockable && (
        <button type="button" className="why__link" onClick={() => onLock!(change.activity_id)} disabled={busy}>
          원래대로 두기
        </button>
      )}
      {restore.kind === 'error' && <span className="why__note">계산하지 못했어요. 다시 눌러 주세요.</span>}
      {restore.kind === 'done' && restore.cf === null && <span className="why__note">살리면 맞는 일정이 없어요</span>}
    </div>
  )
}
