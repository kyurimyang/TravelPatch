// A stitched patch, kept as the list of changes against the day it was applied to (CLAUDE.md
// invariant 6), plus how to apply it to the trip and take it back off ("실 풀기").
// Only the user's own titles and times are kept: no coordinates and no Google names (a substitute
// is recorded as "substituted", not by the name of the place).
import type { DisruptionEvent, Op, RecoveryResult } from '../api/types'
import type { Trip, TripItem } from '../store/trip'

type Slot = { start: number; end: number }

export type PatchChange = {
  itemId: string
  op: Op
  before: Slot | null
  after: Slot | null
  /** op "add" (MUST_VISIT): the new piece itself, the user's words and Google place id only. */
  added?: { title: string; category: TripItem['category']; placeId: string | null }
}

export type SavedPatch = {
  id: string
  /** ISO date of the trip day it was stitched onto. */
  date: string
  /** ISO timestamp, for the patch list. */
  savedAt: string
  strategy: string
  preservationRate: number
  /** What the user said happened, as the chips showed it. */
  chips: string[]
  /** The kind of hole (DELAY, WEATHER, ...), for the patch list and badges. */
  eventType: DisruptionEvent['type'] | null
  changes: PatchChange[]
}

export function patchFrom(
  id: string,
  date: string,
  result: RecoveryResult,
  chips: string[],
  savedAt: string,
  eventType: DisruptionEvent['type'] | null = null,
  added: PatchChange['added'] | null = null,
): SavedPatch {
  return {
    id,
    date,
    savedAt,
    strategy: result.strategy,
    preservationRate: result.preservation_rate,
    chips,
    eventType,
    changes: result.changes
      .filter((c) => c.op !== 'keep')
      .map((c) => ({
        itemId: c.activity_id,
        op: c.op,
        before: c.before ?? null,
        after: c.after ?? null,
        ...(c.op === 'add' && added ? { added } : {}),
      })),
  }
}

function mapDay(trip: Trip, date: string, f: (it: TripItem) => TripItem): Trip['days'] {
  return trip.days.map((d) => (d.date === date ? { ...d, items: d.items.map(f) } : d))
}

/** The trip with the patch applied and recorded. Applying the same patch id twice does nothing. */
export function applyPatch(trip: Trip, patch: SavedPatch): Trip {
  if (trip.patches.some((p) => p.id === patch.id)) return trip
  const byItem = new Map(patch.changes.map((c) => [c.itemId, c]))
  const days = mapDay(trip, patch.date, (it) => {
    const c = byItem.get(it.id)
    if (!c) return it
    if (c.op === 'drop') return { ...it, dropped: true, patched: true }
    if (!c.after) return it
    return {
      ...it,
      start: c.after.start,
      end: c.after.end,
      substituted: c.op === 'substitute' || it.substituted,
      patched: true,
    }
  })
  // An added place (MUST_VISIT) becomes a piece of the day: a must, where the patch put it.
  const adds = patch.changes.filter((c) => c.op === 'add' && c.after && c.added)
  const withAdds = adds.length
    ? days.map((d) =>
        d.date !== patch.date
          ? d
          : {
              ...d,
              items: [
                ...d.items,
                ...adds.map(
                  (c): TripItem => ({
                    id: c.itemId,
                    title: c.added!.title,
                    category: c.added!.category,
                    start: c.after!.start,
                    end: c.after!.end,
                    durationEstimated: false,
                    reservationTime: null,
                    note: null,
                    placeId: c.added!.placeId,
                    tier: 'must',
                    patched: true,
                  }),
                ),
              ].sort((a, b) => (a.start ?? 0) - (b.start ?? 0)),
            },
      )
    : days
  return { ...trip, days: withAdds, patches: [...trip.patches, patch] }
}

/** Take a patch back off: every changed item returns to its `before` slot. Only the latest patch
 * of a day can be undone, so later patches never rest on a slot that no longer exists. */
export function undoPatch(trip: Trip, patchId: string): Trip {
  const patch = trip.patches.find((p) => p.id === patchId)
  if (!patch) return trip
  const later = trip.patches.filter((p) => p.date === patch.date)
  if (later[later.length - 1]?.id !== patchId) return trip
  const byItem = new Map(patch.changes.map((c) => [c.itemId, c]))
  const stillPatched = new Set(
    trip.patches.filter((p) => p.id !== patchId).flatMap((p) => p.changes.map((c) => c.itemId)),
  )
  const addedIds = new Set(patch.changes.filter((c) => c.op === 'add').map((c) => c.itemId))
  const days = mapDay(trip, patch.date, (it) => {
    const c = byItem.get(it.id)
    if (!c || !c.before) return it
    return {
      ...it,
      start: c.before.start,
      end: c.before.end,
      dropped: false,
      substituted: c.op === 'substitute' ? false : it.substituted,
      patched: stillPatched.has(it.id),
    }
  })
  const without = days.map((d) => (d.date === patch.date ? { ...d, items: d.items.filter((it) => !addedIds.has(it.id)) } : d))
  return { ...trip, days: without, patches: trip.patches.filter((p) => p.id !== patchId) }
}
