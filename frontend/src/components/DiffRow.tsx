import type { Op, RecoveryChange } from '../api/types'
import { formatSlot } from '../lib/time'
import './DiffRow.css'

// The chip always carries text, so color is never the only signal (CLAUDE.md section 8).
const OP_LABEL: Record<Op, string> = {
  keep: '유지',
  move: '이동',
  shrink: '단축',
  drop: '삭제',
  substitute: '대체',
  extend: '연장',
  add: '추가',
}

function duration(slot: { start: number; end: number }): number {
  return slot.end - slot.start
}

function TimeLine({ change }: { change: RecoveryChange }) {
  const { before, after, op } = change
  if (op === 'drop' && before) {
    return <s className="diff-row__time">{formatSlot(before.start, before.end)}</s>
  }
  if (op === 'keep' && after) {
    return <span className="diff-row__time">{formatSlot(after.start, after.end)}</span>
  }
  if (before && after) {
    return (
      <span className="diff-row__time">
        <s>{formatSlot(before.start, before.end)}</s> → {formatSlot(after.start, after.end)}
        {op === 'shrink' && ` (${duration(before)}분 → ${duration(after)}분)`}
      </span>
    )
  }
  if (after) {
    return <span className="diff-row__time">{formatSlot(after.start, after.end)}</span>
  }
  return null
}

interface Props {
  title: string
  change: RecoveryChange
}

export function DiffRow({ title, change }: Props) {
  return (
    <li className="diff-row" data-op={change.op}>
      <div className="diff-row__head">
        <span className="diff-row__title">{title}</span>
        <span className="diff-row__chip">{OP_LABEL[change.op]}</span>
      </div>
      <TimeLine change={change} />
      {change.needs_check && <span className="diff-row__check">현장 확인 필요</span>}
    </li>
  )
}
