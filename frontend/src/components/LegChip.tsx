import type { TravelMode, TravelTime } from '../api/types'
import './LegChip.css'

// Words, not just an icon: the mode is never told by a symbol or a colour alone (CLAUDE.md 8).
const MODE_LABEL: Record<TravelMode, string> = { transit: '대중교통', walk: '도보', car: '자동차' }

type Props = {
  mode: TravelMode
  minutes: number
  /** "api" = Google's real time; "estimate" = our guess from the distance. Said out loud. */
  source: TravelTime['source']
}

// The way between two places: "대중교통 약 20분". An estimate says so ("추정"), so a guess is
// never read as a measured time.
export function LegChip({ mode, minutes, source }: Props) {
  return (
    <li className="leg-chip" data-source={source}>
      <span className="leg-chip__line" aria-hidden="true" />
      <span className="leg-chip__text">
        {MODE_LABEL[mode]} 약 {minutes}분{source === 'estimate' && <em> · 추정</em>}
      </span>
    </li>
  )
}
