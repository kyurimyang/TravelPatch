import { useState } from 'react'
import type { BuiltPlan, EventDraft, InterpretResponse, Question, Wish } from '../api/types'
import { answer, TYPE_CHOICES, WISH_LABEL } from '../lib/eventChips'
import { minutesLabel } from '../lib/quick'
import { formatTime, parseTime } from '../lib/time'
import './EventChips.css'

type Activity = BuiltPlan['activities'][number]

type Props = {
  response: InterpretResponse
  activities: Pick<Activity, 'id' | 'title' | 'planned_start'>[]
  now: number
  busy: boolean
  /** The drafts and wishes after an edit: the caller runs the rules again (no LLM). */
  onChange: (drafts: EventDraft[], wishes: Wish[]) => void
  /** "꼭 가고 싶은 곳": words are not enough, the place is picked on the map. */
  onAddPlace: () => void
}

/** "이렇게 이해했어요" for a typed sentence: one chip per event (fix it or take it out), and for
 * an event still missing something, the question with a tap to answer. Wishes as chips too. */
export function EventChips({ response, activities, now, busy, onChange, onAddPlace }: Props) {
  const [editing, setEditing] = useState<number | null>(null)
  const drafts = response.items.map((i) => i.draft)
  const wishes = response.wishes
  const titleOf = (id: string) => activities.find((a) => a.id === id)
  const change = (next: EventDraft[], nextWishes: Wish[] = wishes) => {
    setEditing(null)
    onChange(next, nextWishes)
  }
  const reply = (index: number, q: Question, value: number | string) =>
    change(drafts.map((d, i) => (i === index ? answer(d, q, value) : d)))
  const remove = (index: number) => change(drafts.filter((_, i) => i !== index))

  return (
    <div className="event-chips">
      <ul>
        {response.items.map((item, i) => {
          const asking = item.event == null || editing === i
          return (
            <li key={i} className={item.event == null ? 'event-chips__open' : undefined}>
              <div className="event-chips__row">
                {item.event != null ? (
                  <span className="event-chips__chip">
                    {item.chip}
                    {item.assumed && <em>확인해 주세요</em>}
                  </span>
                ) : (
                  <span className="event-chips__question">{item.question?.text ?? '어떤 일이 있었나요?'}</span>
                )}
                <span className="event-chips__actions">
                  {item.event != null && item.question && (
                    <button type="button" disabled={busy} aria-expanded={editing === i} onClick={() => setEditing(editing === i ? null : i)}>
                      고치기
                    </button>
                  )}
                  <button type="button" disabled={busy} onClick={() => remove(i)}>
                    빼기
                  </button>
                </span>
              </div>
              {asking && item.question && (
                <Answer
                  question={item.question}
                  showText={item.event != null}
                  now={now}
                  busy={busy}
                  titleOf={titleOf}
                  onAnswer={(v) => reply(i, item.question!, v)}
                  onAddPlace={onAddPlace}
                />
              )}
            </li>
          )
        })}
        {response.wish_chips.map(({ wish, text }) => (
          <li key={wish}>
            <div className="event-chips__row">
              <span className="event-chips__chip" title={WISH_LABEL[wish]}>
                {text}
              </span>
              <span className="event-chips__actions">
                <button type="button" disabled={busy} onClick={() => change(drafts, wishes.filter((x) => x !== wish))}>
                  빼기
                </button>
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Answer({
  question,
  showText,
  now,
  busy,
  titleOf,
  onAnswer,
  onAddPlace,
}: {
  question: Question
  showText: boolean
  now: number
  busy: boolean
  titleOf: (id: string) => Pick<Activity, 'title' | 'planned_start'> | undefined
  onAnswer: (value: number | string) => void
  onAddPlace: () => void
}) {
  const [time, setTime] = useState(formatTime(question.default ?? now))
  return (
    <div className="event-chips__answer" role="group" aria-label={question.text}>
      {showText && <span>{question.text}</span>}
      <div className="event-chips__options">
        {question.kind === 'minutes' &&
          question.options.map((m) => (
            <button key={m} type="button" disabled={busy} onClick={() => onAnswer(m)}>
              {minutesLabel(m)}
            </button>
          ))}
        {question.kind === 'place' &&
          question.candidates.map((id) => {
            const a = titleOf(id)
            return (
              <button key={id} type="button" disabled={busy} onClick={() => onAnswer(id)}>
                {a ? `${formatTime(a.planned_start)} ${a.title}` : id}
              </button>
            )
          })}
        {question.kind === 'type' &&
          TYPE_CHOICES.map((c) => (
            <button key={c.type} type="button" disabled={busy} onClick={() => onAnswer(c.type)}>
              {c.label}
            </button>
          ))}
        {question.kind === 'time' && (
          <>
            <input type="time" step={300} value={time} aria-label={question.text} onChange={(e) => setTime(e.target.value)} />
            <button
              type="button"
              disabled={busy || parseTime(time) === null}
              onClick={() => {
                const m = parseTime(time)
                if (m !== null) onAnswer(m)
              }}
            >
              이 시각으로
            </button>
            {question.field === 'time_from' && (
              <button type="button" disabled={busy} onClick={() => onAnswer(now)}>
                지금부터
              </button>
            )}
          </>
        )}
        {question.kind === 'add_place' && (
          <button type="button" disabled={busy} onClick={onAddPlace}>
            지도에서 고르기
          </button>
        )}
      </div>
    </div>
  )
}
