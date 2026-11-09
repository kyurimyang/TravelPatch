// TEMPORARY hand-written mirror of backend/app/schemas (recovery.py, enums.py).
// CLAUDE.md wants these generated from the backend OpenAPI; replace this file once
// the FastAPI app exists. Times are minutes since midnight, like the backend.

export type Op = 'keep' | 'move' | 'shrink' | 'drop' | 'substitute' | 'extend' | 'add'

export type ReasonType = 'binding' | 'value' | 'counterfactual'

export interface Slot {
  start: number
  end: number
}

export interface RecoveryChange {
  activity_id: string
  op: Op
  before: Slot | null
  after: Slot | null
  reason_type: ReasonType | null
  substitute_id: string | null
  needs_check: boolean
}

export interface RecoveryResult {
  strategy: string
  changes: RecoveryChange[]
  rc_total: number
  preservation_rate: number
  violations: number
  solver_ms: number
}

// What the UI needs to name an activity. The engine's changes only carry the id.
export interface ActivityInfo {
  id: string
  title: string
  category: string
}
