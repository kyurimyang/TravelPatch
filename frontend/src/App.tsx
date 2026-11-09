import type { ActivityInfo, RecoveryResult } from './api/types'
import { CandidateCard } from './components/CandidateCard'
import mock from './mocks/scenarioA.json'
import './App.css'

// Mock = real engine output for scenario A (see docs/decisions.md 2026-11-09).
const activities = mock.activities as ActivityInfo[]
const results = mock.results as RecoveryResult[]

const titleOf = new Map(activities.map((a) => [a.id, a.title]))

export default function App() {
  return (
    <main className="app">
      {results.map((result) => (
        <CandidateCard key={result.strategy} result={result} titleOf={titleOf} />
      ))}
    </main>
  )
}
