import type { TravelMode } from '../api/types'
import './TravelModePicker.css'

const MODES: { value: TravelMode; label: string; hint: string }[] = [
  { value: 'transit', label: '대중교통', hint: '지하철·버스' },
  { value: 'walk', label: '도보', hint: '걸어서만' },
  { value: 'car', label: '자동차', hint: '택시·렌터카' },
]

type Props = {
  name: string
  value: TravelMode
  onChange: (mode: TravelMode) => void
}

// One choice per trip; travel times between places are estimated with it.
export function TravelModePicker({ name, value, onChange }: Props) {
  return (
    <div className="travel-mode" role="radiogroup" aria-label="이동수단">
      {MODES.map((m) => (
        <label key={m.value} className="travel-mode__option">
          <input
            type="radio"
            name={name}
            value={m.value}
            checked={value === m.value}
            onChange={() => onChange(m.value)}
          />
          <b>{m.label}</b>
          <span>{m.hint}</span>
        </label>
      ))}
    </div>
  )
}
