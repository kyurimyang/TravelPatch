import { useState } from 'react'
import { formatTime, parseTime } from '../lib/time'
import './TimeEditor.css'

type Props = {
  idPrefix: string
  start: number | null
  end: number | null
  onSave: (start: number, end: number) => void
  onCancel?: () => void
}

// Two clock inputs for one itinerary item. Saves only a range the engine can use (end after start).
export function TimeEditor({ idPrefix, start, end, onSave, onCancel }: Props) {
  const [from, setFrom] = useState(start != null ? formatTime(start) : '')
  const [to, setTo] = useState(end != null ? formatTime(end) : '')

  const s = parseTime(from)
  const e = parseTime(to)
  const valid = s !== null && e !== null && e > s

  return (
    <div className="time-editor">
      <div className="time-editor__row">
        <label htmlFor={`${idPrefix}-from`}>시작</label>
        <input id={`${idPrefix}-from`} type="time" step={300} value={from} onChange={(ev) => setFrom(ev.target.value)} />
        <label htmlFor={`${idPrefix}-to`}>끝</label>
        <input id={`${idPrefix}-to`} type="time" step={300} value={to} onChange={(ev) => setTo(ev.target.value)} />
      </div>
      {s !== null && e !== null && !valid && <p className="time-editor__warn">끝나는 시각이 시작보다 늦어야 해요</p>}
      <div className="time-editor__actions">
        {onCancel && (
          <button type="button" className="time-editor__quiet" onClick={onCancel}>
            취소
          </button>
        )}
        <button type="button" disabled={!valid} onClick={() => valid && onSave(s, e)}>
          저장
        </button>
      </div>
    </div>
  )
}
