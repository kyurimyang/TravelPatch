// The quick buttons on Recover, turned straight into an event by rules (decision 2026-11-23).
// They used to fill in a sentence for the LLM, so the most stressful moment of the trip took a
// tap, an LLM round trip, a reading of what it understood, then the patch. Now: a tap, one
// choice (how long, which place, from when), the patch. Typing a sentence still goes to the LLM.
import type { BuiltPlan, DisruptionEvent, InterpretResponse } from '../api/types'
import { formatTime } from './time'

export type QuickKind = 'delay' | 'closed' | 'rain' | 'late' | 'tired' | 'add'

/** What one tap still has to ask, or nothing (tired: there is nothing to choose). */
export type QuickAsk =
  | { kind: 'minutes'; label: string; options: number[] }
  | { kind: 'place'; label: string }
  | { kind: 'from'; label: string; options: number[] }
  | { kind: 'search'; label: string; options: number[] }
  | null

export const QUICK_ASK: Record<QuickKind, QuickAsk> = {
  delay: { kind: 'minutes', label: '얼마나 늦어져요?', options: [15, 30, 60, 90] },
  late: { kind: 'minutes', label: '얼마나 늦게 출발해요?', options: [30, 60, 120, 180] },
  closed: { kind: 'place', label: '어디가 닫았어요?' },
  rain: { kind: 'from', label: '언제부터 와요?', options: [0, 30, 60, 120] },
  tired: null,
  // MUST_VISIT: a place to pick on the map, then how long (the server builds the event).
  add: { kind: 'search', label: '어디를 넣을까요?', options: [30, 60, 90, 120] },
}

export function minutesLabel(m: number): string {
  if (m === 0) return '지금'
  if (m < 60) return `${m}분`
  return m % 60 ? `${Math.floor(m / 60)}시간 ${m % 60}분` : `${m / 60}시간`
}

/** The places that can still be closed on the user: not over yet by `now`, in planned order. */
export function closable(plan: BuiltPlan, now: number): BuiltPlan['activities'] {
  return plan.activities.filter((a) => a.planned_end > now)
}

function ok(event: DisruptionEvent, chips: string[]): InterpretResponse {
  return { status: 'ok', interpretation: null, event, chips, problem: null }
}

/** The event (and the chips shown for it) for a quick button and the choice made under it.
 *  `value`: minutes for delay/late/rain, an activity id for closed, ignored for tired. */
export function quickResponse(
  kind: QuickKind,
  value: number | string | null,
  now: number,
  where: string,
  titleOf: (id: string) => string,
): InterpretResponse {
  const end = (m: number) => Math.min(now + m, 24 * 60)
  switch (kind) {
    case 'delay':
    case 'late': {
      const at = end(Number(value))
      return ok({ type: 'DELAY', occurred_at: now, start_time: at, location_id: where }, [`${formatTime(at)}부터 움직일 수 있어요`])
    }
    case 'rain': {
      const at = end(Number(value))
      return ok({ type: 'WEATHER', occurred_at: now, start_time: at, end_time: null, location_id: where }, [
        `${formatTime(at)}부터 비 · 끝나는 시각 미정`,
      ])
    }
    case 'closed':
      return ok({ type: 'CLOSURE', occurred_at: now, activity_id: String(value), location_id: where }, [
        `${titleOf(String(value))} · 문을 닫았어요`,
      ])
    case 'tired':
      return ok({ type: 'FATIGUE', occurred_at: now, walking_ratio: 0.5, location_id: where }, ['많이 걷는 조각을 줄여요'])
    case 'add':
      // Needs a place lookup first (POST /plans/add-place); Recover builds this one itself.
      throw new Error('quickResponse: "add" goes through addPlace')
  }
}
