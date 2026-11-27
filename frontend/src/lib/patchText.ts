// What a candidate does, said the way the rest of the app talks (a sewing note, not a metrics
// row). Replaces "보존율 96% · 삭제 0 · 단축 2 · 위반 0" (2026-11-24): "위반" is always 0 by design
// (the validator never lets one through), and the counters read like a dashboard.
import type { RecoveryResult } from '../api/types'
import { shiftLabel, timeShift } from './shift'

function counts(r: Pick<RecoveryResult, 'changes'>) {
  const n = (op: string) => r.changes.filter((c) => c.op === op).length
  return { drop: n('drop'), shrink: n('shrink'), sub: n('substitute'), add: n('add') }
}

/** One short line for a candidate's tab: what it gives up, then how much the day moves. */
export function tabLine(r: Pick<RecoveryResult, 'changes'>): string {
  const c = counts(r)
  const parts = [c.drop > 0 ? `${c.drop}곳 빼고` : '빼는 곳 없이']
  if (c.sub > 0) parts.push(`${c.sub}곳 근처로`)
  const shift = shiftLabel(timeShift(r))
  if (shift) parts.push(shift.replace('평균 ', '').replace('늦춤', '밀림').replace('당김', '당김'))
  else if (c.shrink > 0) parts.push(`${c.shrink}곳 짧게`)
  return parts.join(' · ')
}

/** The note under the tabs: the whole candidate in one sentence-like line. */
export function patchNote(r: Pick<RecoveryResult, 'changes' | 'preservation_rate'>): string[] {
  const c = counts(r)
  const rate = Math.floor(r.preservation_rate * 100)
  // 100% kept but moved: "100% 그대로 · 2시간 늦게" read as a contradiction (user test 2026-11-27).
  const moved = r.changes.some((ch) => ch.op !== 'keep')
  const out = [rate >= 100 && moved ? '빼거나 줄인 곳 없어요' : `원래 계획 ${rate}% 그대로`]
  if (c.drop > 0) out.push(`${c.drop}곳은 오늘 빼요`)
  if (c.sub > 0) out.push(`${c.sub}곳은 근처 다른 곳으로`)
  if (c.add > 0) out.push(`새로 ${c.add}곳 넣어요`)
  if (c.shrink > 0) out.push(`${c.shrink}곳은 짧게`)
  const shift = timeShift(r)
  const label = shiftLabel(shift)
  if (label) out.push(label.replace('늦춤', '늦게').replace('당김', '일찍'))
  return out
}
