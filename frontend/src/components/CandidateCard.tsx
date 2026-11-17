import type { ReactNode } from 'react'
import type { RecoveryChange, RecoveryResult } from '../api/types'
import { DiffRow } from './DiffRow'
import './CandidateCard.css'

interface Props {
  result: RecoveryResult
  /** Names by id, for activities and substitutes alike (their ids never clash). */
  titleOf: ReadonlyMap<string, string>
  /** Patch icon by activity id. */
  iconOf?: ReadonlyMap<string, string>
  /** Optional "왜?" content per changed row. */
  renderDetail?: (change: RecoveryChange) => ReactNode
}

// The chosen candidate as the day's timetable. Its name and summary are shown by the tabs above.
export function CandidateCard({ result, titleOf, iconOf, renderDetail }: Props) {
  return (
    <ul className="candidate-card">
      {result.changes.map((change) => (
        <DiffRow
          key={change.activity_id}
          title={titleOf.get(change.activity_id) ?? change.activity_id}
          icon={iconOf?.get(change.activity_id)}
          substituteTitle={change.substitute_id ? titleOf.get(change.substitute_id) : undefined}
          change={change}
          detail={renderDetail?.(change)}
        />
      ))}
    </ul>
  )
}
