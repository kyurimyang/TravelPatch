import { useEffect, useState } from 'react'
import { createRecovery } from './api/recoveries'
import type { RecoveryInput, RecoveryResponse } from './api/types'
import { BlockerList } from './components/BlockerList'
import { CandidateCard } from './components/CandidateCard'
import sample from './mocks/scenarioAInput.json'
import './App.css'

// Sample input = scenario A (backend/tests/scenarios/scenario_a.json). Until the register screen
// exists, this is the day the app recovers.
const input = sample as unknown as RecoveryInput
const titleOf = new Map(input.activities.map((a) => [a.id, a.title]))

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'done'; response: RecoveryResponse }

export default function App() {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    // `cancelled` drops a stale answer if the effect re-runs (StrictMode runs it twice in dev).
    let cancelled = false
    createRecovery(input)
      .then((response) => !cancelled && setState({ status: 'done', response }))
      .catch((e: Error) => !cancelled && setState({ status: 'error', message: e.message }))
    return () => {
      cancelled = true
    }
  }, [])

  if (state.status === 'loading') return <main className="app">복구안을 계산하고 있어요…</main>
  if (state.status === 'error') {
    return <main className="app">불러오지 못했어요: {state.message}</main>
  }

  const { candidates, blockers } = state.response
  return (
    <main className="app">
      {candidates.length === 0 && <BlockerList blockers={blockers} titleOf={titleOf} />}
      {candidates.map((result) => (
        <CandidateCard key={result.strategy} result={result} titleOf={titleOf} />
      ))}
    </main>
  )
}
