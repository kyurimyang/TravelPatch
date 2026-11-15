import { TIERS, type Tier } from '../lib/tier'
import './TierPicker.css'

type Props = {
  /** Unique per item: groups the radios and is the only thing that ties them together. */
  name: string
  value: Tier
  recommended: Tier
  onChange: (tier: Tier) => void
}

// Three-way radio group. The real <input type="radio"> stays in the DOM (hidden visually only),
// so keyboard and screen-reader behaviour comes from the browser for free.
export function TierPicker({ name, value, recommended, onChange }: Props) {
  return (
    <div className="tier-picker">
      {TIERS.map((t) => (
        <label key={t.value} className={`tier-picker__opt tier-picker__opt--${t.value}`}>
          <input type="radio" name={name} checked={value === t.value} onChange={() => onChange(t.value)} />
          {t.label}
          {recommended === t.value && <span className="tier-picker__rec">추천</span>}
        </label>
      ))}
    </div>
  )
}
