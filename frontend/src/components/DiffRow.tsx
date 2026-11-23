import type { ReactNode } from 'react'
import type { Op, RecoveryChange } from '../api/types'
import { formatSlot, formatTime } from '../lib/time'
import { josaFor } from '../lib/josa'
import './DiffRow.css'

// The chip always carries text, so color is never the only signal (CLAUDE.md section 8).
export const OP_LABEL: Record<Op, string> = {
  keep: '유지',
  move: '이동',
  shrink: '단축',
  drop: '삭제',
  substitute: '대체',
  extend: '연장',
  add: '추가',
}

const minutes = (slot: { start: number; end: number }) => slot.end - slot.start

/** One line saying what happens to this piece, in the user's terms. */
function ChangeLine({ change, substituteTitle }: { change: RecoveryChange; substituteTitle?: string }) {
  const { before, after, op } = change
  if (op === 'keep' && after) return <span className="diff-row__change">{formatSlot(after.start, after.end)} 그대로</span>
  if (op === 'drop' && before) {
    return (
      <span className="diff-row__change">
        <s>{formatSlot(before.start, before.end)}</s> 오늘은 빼요
      </span>
    )
  }
  if (op === 'add' && after) {
    return <span className="diff-row__change">새로 넣어요 · {formatSlot(after.start, after.end)}</span>
  }
  if (op === 'substitute') {
    return (
      <span className="diff-row__change">
        <b>{substituteTitle ?? '근처 다른 곳'}</b>
        {josaFor(substituteTitle ?? '근처 다른 곳', '으로/로')} 바꿔요
        {after && ` · ${formatSlot(after.start, after.end)}`}
      </span>
    )
  }
  if (before && after) {
    return (
      <span className="diff-row__change">
        <s>{formatSlot(before.start, before.end)}</s> → {formatSlot(after.start, after.end)}
        {(op === 'shrink' || op === 'extend') && ` · ${minutes(before)}분 → ${minutes(after)}분`}
      </span>
    )
  }
  return after ? <span className="diff-row__change">{formatSlot(after.start, after.end)}</span> : null
}

interface Props {
  title: string
  change: RecoveryChange
  /** Category patch icon of the piece. */
  icon?: string
  /** Name of the place a substitute change goes to instead. */
  substituteTitle?: string
  /** "왜?" content, folded under the row. Changed rows only (a kept row needs no reason). */
  detail?: ReactNode
  /** It changed places with a piece around it (lib/timetable). */
  reordered?: boolean
}

// A piece of the day as a row of the timetable: time | patch | name + what changes | op label.
// Changed pieces are stitched on (dashed edge in the op colour); kept pieces stay flat.
export function DiffRow({ title, change, icon, substituteTitle, detail, reordered }: Props) {
  const slot = change.after ?? change.before
  return (
    <li className="diff-row" data-op={change.op}>
      <span className="diff-row__time">{slot ? formatTime(slot.start) : '--:--'}</span>
      {icon && <img className="diff-row__icon" src={icon} alt="" aria-hidden="true" />}
      <div className="diff-row__main">
        <div className="diff-row__head">
          <b className="diff-row__title">{title}</b>
          <span className="diff-row__chip">{OP_LABEL[change.op]}</span>
        </div>
        <ChangeLine change={change} substituteTitle={substituteTitle} />
        {reordered && <span className="diff-row__reordered">순서 바뀜</span>}
        {change.needs_check && <span className="diff-row__check">현장 확인 필요</span>}
        {detail && change.op !== 'keep' && (
          <details className="diff-row__why">
            <summary>왜 바뀌었나요?</summary>
            {detail}
          </details>
        )}
      </div>
    </li>
  )
}
