// How far a plan moved the pieces it kept. The preservation rate counts only what was dropped,
// shortened or swapped, so a day pushed back two hours still reads "100%"; this is the other
// half, shown next to it so the number does not overstate how unchanged the day is.
import type { RecoveryResult } from '../api/types'

export type TimeShift = { moved: number; avgMinutes: number }

/** Pieces kept at the same place whose start changed, and their average shift (+ later, - earlier),
 *  rounded to 5 minutes. null when nothing kept moved. */
export function timeShift(result: Pick<RecoveryResult, 'changes'>): TimeShift | null {
  const shifts = result.changes
    .filter((c) => c.op !== 'drop' && c.op !== 'substitute' && c.before && c.after)
    .map((c) => c.after!.start - c.before!.start)
    .filter((d) => d !== 0)
  if (shifts.length === 0) return null
  const avg = shifts.reduce((a, b) => a + b, 0) / shifts.length
  return { moved: shifts.length, avgMinutes: Math.round(avg / 5) * 5 }
}

/** "평균 40분 늦춤" / "평균 15분 당김"; null when the average is under 5 minutes either way. */
export function shiftLabel(shift: TimeShift | null): string | null {
  if (!shift || shift.avgMinutes === 0) return null
  const m = Math.abs(shift.avgMinutes)
  const amount = m >= 60 ? `${Math.floor(m / 60)}시간${m % 60 ? ` ${m % 60}분` : ''}` : `${m}분`
  return `평균 ${amount} ${shift.avgMinutes > 0 ? '늦춤' : '당김'}`
}

/** "3곳의 시작이 평균 40분 늦춰졌어요." for the finished screen; null as shiftLabel. */
export function shiftSentence(shift: TimeShift | null): string | null {
  const label = shiftLabel(shift)
  if (!shift || !label) return null
  const amount = label.replace(/^평균 /, '').replace(/ (늦춤|당김)$/, '')
  return `${shift.moved}곳의 시작이 평균 ${amount} ${shift.avgMinutes > 0 ? '늦춰졌어요' : '당겨졌어요'}.`
}
