// Why each change was made, in Korean, filled ONLY from the engine's own reason data
// (CLAUDE.md invariant 5: numbers and names never come from an LLM). No reason established ->
// nothing is said (the time change on the row already shows what happened, 2026-11-27).
import type { DisruptionEvent, RecoveryChange } from '../api/types'

const TIER_BY_VALUE: Record<number, string> = { 5: '꼭', 3: '좋음', 1: '선택' }

// Broken by the original slot on its own (with the event), whatever else moves: locking the piece
// back there always fails. travel / deadline / reservation can clear once other pieces move.
const SELF_BOUND = new Set(['past', 'closure', 'hours', 'weather', 'fatigue'])

/** Whether "이건 원래대로 둘래요 (고정)" can work for this change (A4: it was shown where it never can). */
export function canLock(change: RecoveryChange): boolean {
  // An extension is the user's own ask: "leave it as it was" would undo the request itself.
  if (change.op === 'keep' || change.op === 'drop' || change.op === 'extend' || change.op === 'add') return false
  const forced = change.reason_type === 'binding' ? (change.reason_data?.forced_by ?? []) : []
  return !forced.some((k) => SELF_BOUND.has(k))
}

// The same reasons as a short tag next to the change (2026-11-27): the full sentence under a
// "왜 바뀌었나요?" fold was one more thing to open and read. Same sources, fewer words.
const TAG: Record<string, string> = {
  past: '시간이 지나서',
  meal_window: '식사 시간대',
  reservation_buffer: '예약 여유',
  no_drop: '이 안의 규칙',
  closure: '문 닫아서',
  reservation: '예약 시각 때문에',
  hours: '영업시간 때문에',
  weather: '비 때문에',
  fatigue: '덜 걸으려고',
  deadline: '숙소 복귀 시각',
  travel: '앞 일정이 밀려서',
  event: '말씀하신 대로',
  in_progress: '지금 하는 중',
  duration: '최소 시간',
}

/** The tag a piece gets from an event that names it ("점심 대기 40분"): the user's own words back,
 * numbers from the event itself. First event that names the piece wins. */
function eventTag(change: RecoveryChange, events: DisruptionEvent[]): string | null {
  for (const e of events) {
    if (!('activity_id' in e) || e.activity_id !== change.activity_id) continue
    switch (e.type) {
      case 'WAIT':
        return `대기 ${e.minutes}분 포함`
      case 'RESERVATION_CHANGE':
        return '예약이 바뀌어서'
      case 'EXTEND':
        return '말씀하신 대로'
      case 'CLOSURE':
        return '문 닫아서'
    }
  }
  return null
}

/** A few words saying why, or null when the engine has no single reason (never invented).
 * `event` is the main event; `more` the rest of the same sentence. */
export function reasonTag(change: RecoveryChange, event?: DisruptionEvent, more: DisruptionEvent[] = []): string | null {
  const named = eventTag(change, event ? [event, ...more] : more)
  if (named) return named
  const data = change.reason_data
  if (change.reason_type === 'binding' && data?.forced_by.length) {
    const kind = data.forced_by[0]
    if (kind === 'past' && event?.type === 'DELAY') return '늦어져서'
    return TAG[kind] ?? null
  }
  if (change.reason_type === 'value' && data?.value != null && (change.op === 'drop' || change.op === 'shrink')) {
    const tier = TIER_BY_VALUE[data.value]
    return tier ? `‘${tier}’ 일정이라` : null
  }
  if (change.op === 'substitute') return '원래 곳에 못 가서'
  return null
}
