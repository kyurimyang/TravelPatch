import { Fragment, type ReactNode } from 'react'
import type { RecoveryChange, RecoveryResult, TravelMode, TravelTime } from '../api/types'
import { legIntoEach } from '../lib/legs'
import { timetable } from '../lib/timetable'
import { DiffRow } from './DiffRow'
import { LegChip } from './LegChip'
import './CandidateCard.css'

interface Props {
  result: RecoveryResult
  /** Names by id, for activities and substitutes alike (their ids never clash). */
  titleOf: ReadonlyMap<string, string>
  /** Patch icon by activity id. */
  iconOf?: ReadonlyMap<string, string>
  /** Optional actions per changed row (살리기 / 원래대로). */
  renderDetail?: (change: RecoveryChange) => ReactNode
  /** Optional short reason per changed row ("비 때문에"). */
  tagOf?: (change: RecoveryChange) => string | null
  /** With both, the way between neighbouring places is shown between rows. */
  travel?: readonly TravelTime[]
  mode?: TravelMode
}

// The chosen candidate as the day's timetable. Its name and summary are shown by the tabs above.
export function CandidateCard({ result, titleOf, iconOf, renderDetail, tagOf, travel, mode }: Props) {
  const rows = timetable(result.changes)
  // Where the traveler really goes, in order: a dropped piece is not visited, and a substitute
  // is visited in place of the original.
  const stopOf = (c: RecoveryChange) => c.substitute_id ?? c.activity_id
  const stops = rows.filter(({ change }) => change.after).map(({ change }) => stopOf(change))
  const legInto = travel && mode ? legIntoEach(stops, travel) : null
  return (
    <ul className="candidate-card">
      {rows.map(({ change, reordered }) => {
        const leg = change.after ? legInto?.get(stopOf(change)) : undefined
        return (
          <Fragment key={change.activity_id}>
            {leg && mode && <LegChip mode={mode} minutes={leg.minutes} source={leg.source} />}
            <DiffRow
              reordered={reordered}
              title={titleOf.get(change.activity_id) ?? change.activity_id}
              icon={iconOf?.get(change.activity_id)}
              substituteTitle={change.substitute_id ? titleOf.get(change.substitute_id) : undefined}
              change={change}
              tag={tagOf?.(change)}
              detail={renderDetail?.(change)}
            />
          </Fragment>
        )
      })}
    </ul>
  )
}
