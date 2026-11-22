// The diff list as a timetable (review 2026-11-19, A3): rows in the new time order, so times
// always read forwards, with "순서 바뀜" on pieces that changed places.
import type { RecoveryChange } from '../api/types'

export type TimetableRow = { change: RecoveryChange; reordered: boolean }

const planned = (c: RecoveryChange) => c.before?.start ?? c.after?.start ?? 0
// A dropped piece keeps its planned slot in the list: what is missing shows where it was.
const shown = (c: RecoveryChange) => c.after?.start ?? planned(c)
const moved = (c: RecoveryChange) => (c.after ? Math.abs(c.after.start - planned(c)) : 0)

export function timetable(changes: readonly RecoveryChange[]): TimetableRow[] {
  // Ties: planned start, then id, so the same result always lists the same way.
  const rows = [...changes].sort(
    (x, y) => shown(x) - shown(y) || planned(x) - planned(y) || x.activity_id.localeCompare(y.activity_id),
  )
  // A swapped pair (the pairs Kendall tau counts in D_order) marks the piece that moved further,
  // both when equal: a reserved piece that stayed put is not what changed places.
  const placed = rows.filter((c) => c.after)
  const marked = new Set<string>()
  for (let i = 0; i < placed.length; i++) {
    for (let j = i + 1; j < placed.length; j++) {
      const [early, late] = [placed[i], placed[j]] // early comes first now
      if (planned(early) <= planned(late)) continue // same order as planned
      const d = moved(early) - moved(late)
      if (d >= 0) marked.add(early.activity_id)
      if (d <= 0) marked.add(late.activity_id)
    }
  }
  return rows.map((change) => ({ change, reordered: marked.has(change.activity_id) }))
}
