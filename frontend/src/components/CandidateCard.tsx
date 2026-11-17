import type { ReactNode } from 'react'
import type { RecoveryChange, RecoveryResult } from '../api/types'
import { strategyLabel } from '../lib/strategy'
import { DiffRow } from './DiffRow'
import { SummaryBar } from './SummaryBar'
import './CandidateCard.css'

interface Props {
  result: RecoveryResult
  /** Names by id, for activities and substitutes alike (their ids never clash). */
  titleOf: ReadonlyMap<string, string>
  /** Optional "왜?" content per changed row. */
  renderDetail?: (change: RecoveryChange) => ReactNode
}

export function CandidateCard({ result, titleOf, renderDetail }: Props) {
  return (
    <section className="candidate-card">
      <h2 className="candidate-card__name">{strategyLabel(result.strategy)}</h2>
      <SummaryBar result={result} />
      <ul className="candidate-card__list">
        {result.changes.map((change) => (
          <DiffRow
            key={change.activity_id}
            title={titleOf.get(change.activity_id) ?? change.activity_id}
            substituteTitle={change.substitute_id ? titleOf.get(change.substitute_id) : undefined}
            change={change}
            detail={renderDetail?.(change)}
          />
        ))}
      </ul>
    </section>
  )
}
