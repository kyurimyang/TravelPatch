// Why each change was made, in Korean, filled ONLY from the engine's own reason data
// (CLAUDE.md invariant 5: numbers and names never come from an LLM). The LLM polishing step can
// later rephrase these sentences, but not add facts.
import type { DisruptionEvent, RecoveryChange } from '../api/types'
import { formatTime } from './time'

// Validator kinds (engine/validator.py) -> what that hard constraint means to a traveller.
const FORCED: Record<string, string> = {
  past: '원래 시각이 이미 지나서 그대로 둘 수 없었어요',
  meal_window: '식사는 원래 시각 앞뒤 1시간 반 안에서만 옮겨요',
  closure: '문을 닫아서 그대로 갈 수 없었어요',
  reservation: '예약 시각을 지키려면 원래 자리에 둘 수 없었어요',
  hours: '원래 시각은 영업시간과 맞지 않았어요',
  weather: '비 오는 시간을 피했어요',
  fatigue: '많이 걷는 일정이라 짧게 줄였어요',
  deadline: '숙소로 돌아갈 시각을 지키려고 했어요',
  travel: '앞 일정이 밀리면서 함께 옮겨졌어요',
  event: '알려 주신 상황 때문이에요',
  in_progress: '지금 하고 있는 일정이에요',
  duration: '이보다 더 짧게 할 수는 없어요',
}
const TIER_BY_VALUE: Record<number, string> = { 5: '꼭', 3: '좋음', 1: '선택' }

// Broken by the original slot on its own (with the event), whatever else moves: locking the piece
// back there always fails. travel / deadline / reservation can clear once other pieces move.
const SELF_BOUND = new Set(['past', 'closure', 'hours', 'weather', 'fatigue'])

/** Whether "이건 원래대로 둘래요 (고정)" can work for this change (A4: it was shown where it never can). */
export function canLock(change: RecoveryChange): boolean {
  if (change.op === 'keep' || change.op === 'drop') return false
  const forced = change.reason_type === 'binding' ? (change.reason_data?.forced_by ?? []) : []
  return !forced.some((k) => SELF_BOUND.has(k))
}

function forcedText(kind: string, event: DisruptionEvent | undefined): string {
  // For a delay "now" is when the user can move again (start_time), not that the time went by.
  if (kind === 'past' && event?.type === 'DELAY') {
    return `${formatTime(event.start_time)}까지 움직일 수 없어서 원래 시각에 갈 수 없었어요`
  }
  return FORCED[kind] ?? '지켜야 하는 조건 때문이에요'
}

/** One or two sentences, or null when the engine established no single reason (never invented).
 * Numbers come from the engine's reason data or the confirmed event, never from an LLM. */
export function describeReason(change: RecoveryChange, event?: DisruptionEvent): string | null {
  const data = change.reason_data
  if (change.reason_type === 'binding' && data) {
    const lines = [...new Set(data.forced_by.map((k) => forcedText(k, event)))]
    return lines.length ? lines.join(' · ') : null
  }
  if (change.reason_type === 'value' && data) {
    const tier = data.value != null ? TIER_BY_VALUE[data.value] : undefined
    const saved = data.minutes_saved
    if (change.op === 'drop') {
      return `${tier ? `‘${tier}’ 일정이라 ` : ''}빼는 쪽을 골랐어요${saved ? `. ${saved}분을 다른 일정에 썼어요` : ''}`
    }
    if (change.op === 'shrink') {
      return `${tier ? `‘${tier}’ 일정이라 ` : ''}${saved ? `${saved}분 줄여서 ` : '조금 줄여서 '}더 중요한 일정을 지켰어요`
    }
  }
  if (change.op === 'substitute') return '원래 장소에 갈 수 없어서 근처의 비슷한 곳으로 바꿨어요'
  return null
}

/** Shown when describeReason has nothing: honest about what we do not know (invariant 8). */
export const NO_SINGLE_REASON = '한 가지 이유로 꼽기는 어려워요. 하루 전체를 맞추는 과정에서 바뀌었어요.'
