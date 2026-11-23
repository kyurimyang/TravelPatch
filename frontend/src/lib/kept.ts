// How much of the original plan a day (or a trip) still holds, read from the trip itself.
// Not a patch's preservation_rate: that one is measured against the day as it was when that
// patch was made, minus the places already visited, so after two patches (or a patch late in the
// day) "원래 계획의 N%" was neither the original plan nor the whole day (found 2026-11-23).
import type { Trip, TripItem } from '../store/trip'

// Same weights as the engine's tiers (backend schemas/enums.py: must 5, nice 3, optional 1).
const WEIGHT: Record<TripItem['tier'], number> = { must: 5, nice: 3, optional: 1 }

/** kept, total: tier weights of what is left of the day's original plan, and of all of it. A
 *  dropped piece keeps 0, a shortened one its share of the original length, a piece moved to
 *  another place half (the visit happens, not where it was planned), anything else all. The
 *  original slot is the one before the first patch that touched the piece. */
function dayWeights(trip: Trip, date: string): { kept: number; total: number } {
  const day = trip.days.find((d) => d.date === date)
  if (!day) return { kept: 0, total: 0 }
  const firstBefore = new Map<string, { start: number; end: number }>()
  for (const p of trip.patches.filter((p) => p.date === date)) {
    for (const c of p.changes) if (c.before && !firstBefore.has(c.itemId)) firstBefore.set(c.itemId, c.before)
  }
  let kept = 0
  let total = 0
  for (const it of day.items) {
    const w = WEIGHT[it.tier] ?? 1
    total += w
    if (it.dropped) continue
    const orig = firstBefore.get(it.id)
    const origLen = orig ? orig.end - orig.start : null
    const nowLen = it.start != null && it.end != null ? it.end - it.start : null
    const share = origLen && nowLen != null ? Math.min(1, nowLen / origLen) : 1
    kept += w * share * (it.substituted ? 0.5 : 1)
  }
  return { kept, total }
}

/** Share (0..1) of a day's original plan still in it; 1 for a day without pieces. */
export function dayKept(trip: Trip, date: string): number {
  const { kept, total } = dayWeights(trip, date)
  return total === 0 ? 1 : kept / total
}

/** Over the days already reached (up to `today`) or patched: future days do not count as 100%. */
export function tripKept(trip: Trip, today: string): number {
  const patched = new Set(trip.patches.map((p) => p.date))
  let kept = 0
  let total = 0
  for (const d of trip.days) {
    if (d.date > today && !patched.has(d.date)) continue
    const w = dayWeights(trip, d.date)
    kept += w.kept
    total += w.total
  }
  return total === 0 ? 1 : kept / total
}
