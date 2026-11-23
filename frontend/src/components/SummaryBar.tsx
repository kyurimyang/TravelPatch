import type { RecoveryResult } from '../api/types'
import { patchNote } from '../lib/patchText'
import './SummaryBar.css'

// A sewn-on label under the candidate tabs: what this patch does to the day, in words
// (lib/patchText). It used to be a row of metric pills (보존율 · 삭제 · 단축 · 위반).
export function SummaryBar({ result }: { result: RecoveryResult }) {
  const [head, ...rest] = patchNote(result)
  return (
    <p className="summary-bar">
      <b>{head}</b>
      {rest.map((t) => (
        <span key={t}>{t}</span>
      ))}
    </p>
  )
}
