import type { RecoveryResult } from '../api/types'
import { strategyLabel } from '../lib/strategy'
import { DiffRow } from './DiffRow'
import { SummaryBar } from './SummaryBar'
import './CandidateCard.css'

interface Props {
  result: RecoveryResult
  titleOf: ReadonlyMap<string, string>
}

export function CandidateCard({ result, titleOf }: Props) {
  return (
    <section className="candidate-card">
      <h2 className="candidate-card__name">{strategyLabel(result.strategy)}</h2>
      <SummaryBar result={result} />
      <ul className="candidate-card__list">
        {result.changes.map((change) => (
          <DiffRow
            key={change.activity_id}
            title={titleOf.get(change.activity_id) ?? change.activity_id}
            change={change}
          />
        ))}
      </ul>
    </section>
  )
}
