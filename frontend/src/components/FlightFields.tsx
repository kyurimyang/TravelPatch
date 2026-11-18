import { useState } from 'react'
import type { PlaceOption } from '../api/types'
import { formatTime, parseTime } from '../lib/time'
import type { TripFlight } from '../store/trip'
import { PlaceSearch } from './PlaceSearch'
import './FlightFields.css'

type Direction = 'arrival' | 'departure'

const TEXT: Record<Direction, { has: string; time: string; buffer: string; defaultBuffer: number; hint: string }> = {
  arrival: {
    has: '도착 항공편이 있어요 (첫날)',
    time: '도착 시각',
    buffer: '공항을 나서기까지',
    defaultBuffer: 60,
    hint: '첫날은 공항에서 시작해요. 입국·짐 찾기에 걸리는 시간이에요.',
  },
  departure: {
    has: '출발 항공편이 있어요 (마지막 날)',
    time: '출발 시각',
    buffer: '공항 도착은 출발',
    defaultBuffer: 180,
    hint: '마지막 날은 공항에서 끝나요. 국제선은 3시간 전 도착을 권해요.',
  },
}

type Props = {
  direction: Direction
  city: string
  value: TripFlight | null
  onChange: (flight: TripFlight | null) => void
}

// One flight, entered by the user (never looked up). Incomplete input is kept on screen only:
// the trip gets a flight once it has a time and an airport.
export function FlightFields({ direction, city, value, onChange }: Props) {
  const t = TEXT[direction]
  const [open, setOpen] = useState(value !== null)
  const [time, setTime] = useState(value ? formatTime(value.time) : '')
  const [airport, setAirport] = useState<{ option: PlaceOption | null; title: string; placeId: string } | null>(
    value ? { option: null, ...value.airport } : null,
  )
  const [buffer, setBuffer] = useState(value?.bufferMinutes != null ? String(value.bufferMinutes) : '')

  function push(next: { time?: string; airport?: typeof airport; buffer?: string }) {
    const m = parseTime(next.time ?? time)
    const a = next.airport === undefined ? airport : next.airport
    const b = (next.buffer ?? buffer).trim()
    const minutes = b === '' ? null : Math.max(0, Math.min(360, Number(b)))
    onChange(m !== null && a ? { time: m, airport: { title: a.title, placeId: a.placeId }, bufferMinutes: minutes } : null)
  }

  return (
    <div className="flight">
      <label className="flight__toggle">
        <input
          type="checkbox"
          checked={open}
          onChange={(e) => {
            setOpen(e.target.checked)
            if (!e.target.checked) onChange(null)
            else push({})
          }}
        />
        {t.has}
      </label>

      {open && (
        <div className="flight__fields">
          <label className="flight__row">
            <span>{t.time}</span>
            <input
              type="time"
              step={300}
              value={time}
              onChange={(e) => {
                setTime(e.target.value)
                push({ time: e.target.value })
              }}
            />
          </label>
          <div className="flight__row flight__row--stack">
            <span>공항</span>
            <PlaceSearch
              inputId={`airport-${direction}`}
              city={city}
              placeholder="예: 하네다 공항"
              picked={airport?.option ?? (airport ? { place_id: airport.placeId, name: airport.title, address: null } : null)}
              onPick={(option, title) => {
                const next = { option, title: title || option.name, placeId: option.place_id }
                setAirport(next)
                push({ airport: next })
              }}
            />
          </div>
          <label className="flight__row">
            <span>{t.buffer}</span>
            <span className="flight__buffer">
              <input
                type="number"
                inputMode="numeric"
                min={0}
                max={360}
                step={10}
                placeholder={String(t.defaultBuffer)}
                value={buffer}
                onChange={(e) => {
                  setBuffer(e.target.value)
                  push({ buffer: e.target.value })
                }}
              />
              분{direction === 'departure' ? ' 전' : ''}
            </span>
          </label>
          <p className="flight__hint">
            {t.hint} 비워 두면 {t.defaultBuffer}분으로 계산해요.
          </p>
        </div>
      )}
    </div>
  )
}
