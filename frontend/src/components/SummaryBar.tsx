import type { Op, RecoveryResult } from '../api/types'
import { shiftLabel, timeShift } from '../lib/shift'
import './SummaryBar.css'

// Count changes per op in one pass; missing ops stay 0.
function countOps(result: RecoveryResult): Record<Op, number> {
  const counts: Record<Op, number> = {
    keep: 0,
    move: 0,
    shrink: 0,
    drop: 0,
    substitute: 0,
    extend: 0,
    add: 0,
  }
  for (const change of result.changes) counts[change.op] += 1
  return counts
}

export function SummaryBar({ result }: { result: RecoveryResult }) {
  const counts = countOps(result)
  // Round down: a plan that changed something must never read as "100%".
  const preservation = Math.floor(result.preservation_rate * 100)
  const shift = shiftLabel(timeShift(result))
  return (
    <p className="summary-bar">
      <strong>보존율 {preservation}%</strong>
      <span>삭제 {counts.drop}</span>
      <span>단축 {counts.shrink}</span>
      {/* The rate ignores time moves: say them, or "100%" overstates an unchanged day. */}
      {shift && <span>{shift}</span>}
      <span>위반 {result.violations}</span>
    </p>
  )
}
