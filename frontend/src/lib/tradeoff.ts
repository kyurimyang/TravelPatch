// "살리면 무엇을 잃나" in a few words (2026-11-27). The counterfactual lists every piece that is
// treated differently; the user only needs the ones that get worse, worst first. Pieces that come
// out the same or better are left out, so "대체 → 대체" or "0%p" never reach the screen.
import type { Counterfactual, RecoveryChange } from '../api/types'
import { formatTime } from './time'

const length = (c: RecoveryChange) => (c.after ? c.after.end - c.after.start : 0)

type Loss = { rank: number; text: string }

function loss(before: RecoveryChange, after: RecoveryChange, title: string, titleOf: (id: string) => string): Loss | null {
  if (!after.after) return before.after ? { rank: 0, text: `${title} 빠짐` } : null
  if (!before.after) return null // was dropped, now kept: a gain
  if (after.substitute_id && after.substitute_id !== before.substitute_id) {
    return { rank: 1, text: `${title} → ${titleOf(after.substitute_id)}` }
  }
  const cut = length(before) - length(after)
  if (cut > 0) return { rank: 2, text: `${title} −${cut}분` }
  // A move is a loss only when it goes farther from the planned time (back to it is a gain).
  const planned = after.before?.start
  const off = (start: number) => (planned == null ? 0 : Math.abs(start - planned))
  if (off(after.after.start) > off(before.after.start)) {
    return { rank: 3, text: `${title} ${formatTime(after.after.start)}부터` }
  }
  return null
}

/** What gets worse if the piece is kept, worst first: drops, swaps, cuts, then moves. At most
 * `max` items; the rest are counted. Empty when nothing else gets worse. */
export function tradeoffs(cf: Counterfactual, titleOf: (id: string) => string, max = 3): string[] {
  const found = cf.side_effects
    .map((s, i) => ({ i, l: loss(s.before, s.after, titleOf(s.activity_id), titleOf) }))
    .filter((x): x is { i: number; l: Loss } => x.l !== null)
    .sort((a, b) => a.l.rank - b.l.rank || a.i - b.i)
    .map((x) => x.l.text)
  if (found.length <= max) return found
  return [...found.slice(0, max), `외 ${found.length - max}곳`]
}
