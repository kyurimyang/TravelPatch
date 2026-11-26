// Editing what the one-line answer understood (decision 2026-11-26). The server's rules turn each
// draft into an event or a question; here the drafts are only changed and sent back
// (POST /disruptions/build). No field name is ever shown: questions come as Korean text.
import type { EventDraft, Question } from '../api/types'
import { formatTime } from './time'

/** The draft with a question's answer filled in. `value`: minutes, a clock time in minutes,
 * an activity id, or an event type, depending on the question. */
export function answer(draft: EventDraft, q: Question, value: number | string): EventDraft {
  switch (q.kind) {
    case 'time':
      // Times travel as "HH:MM", as the user would say them; the server parses them.
      return { ...draft, [q.field]: formatTime(Number(value)) }
    case 'place':
      return { ...draft, activity_id: String(value), activity_hint: null }
    case 'type':
      return { type: String(value) as EventDraft['type'] }
    default:
      // A chosen number replaces a relative shift ("1시간 앞당겨짐") or a default ("지금부터").
      return { ...draft, [q.field]: Number(value) }
  }
}

/** What happened, as the type question offers it: in the user's words, never the type name. */
export const TYPE_CHOICES: { type: EventDraft['type']; label: string }[] = [
  { type: 'DELAY', label: '늦어졌어요' },
  { type: 'WEATHER', label: '비가 와요' },
  { type: 'CLOSURE', label: '문을 닫았어요' },
  { type: 'WAIT', label: '기다려야 해요' },
  { type: 'RESERVATION_CHANGE', label: '예약 시간이 바뀌었어요' },
  { type: 'EXTEND', label: '더 머물고 싶어요' },
  { type: 'FATIGUE', label: '지쳤어요' },
]

export const WISH_LABEL: Record<string, string> = {
  indoor: '실내 우선',
  less_walking: '덜 걷기',
  rest: '쉬기',
}
