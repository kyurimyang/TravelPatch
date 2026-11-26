// Changing a registered trip's plan (decision 2026-11-27, "/trips/:id/edit"). Pure functions:
// the screens decide when, these decide what happens to the trip.
//
// A stitched patch is a change list against the day's plan (CLAUDE.md invariant 6). Editing a
// patched day would leave "실 풀기" restoring slots the user has since changed, so such a day is
// locked until its patches are taken off. A past day is the record of the trip: never editable.
import type { Trip, TripDay, TripItem } from '../store/trip'
import { undoPatch } from './patches'

export type DayLock = 'past' | 'patched'

/** Why the day cannot be edited, or null when it can. A past day stays locked, patched or not. */
export function dayLock(trip: Trip, date: string, today: string): DayLock | null {
  if (date < today) return 'past'
  return trip.patches.some((p) => p.date === date) ? 'patched' : null
}

/** A day's patches taken off, newest first (the only order undoPatch accepts): the plan as it
 *  was before the first one. Their records go with them. */
export function unpatchDay(trip: Trip, date: string): Trip {
  const ids = trip.patches.filter((p) => p.date === date).map((p) => p.id)
  const undone = ids.reverse().reduce(undoPatch, trip)
  // A patch that added a place re-sorted the day; the restored times may want another order.
  return editDay(undone, date, (day) => withItems(day, inTimeOrder(day.items)))
}

/** New times (and what follows from them) for one item; the day is put back in time order. */
export function changeTime(
  trip: Trip,
  date: string,
  itemId: string,
  time: Pick<TripItem, 'start' | 'end' | 'reservationTime'>,
): Trip {
  return editDay(trip, date, (day) => {
    const items = day.items.map((it) => (it.id === itemId ? { ...it, ...time, durationEstimated: false } : it))
    return withItems(day, inTimeOrder(items))
  })
}

export function addItem(trip: Trip, date: string, item: TripItem): Trip {
  return editDay(trip, date, (day) => withItems(day, inTimeOrder([...day.items, item])))
}

/** Take an item out for good. Items that were waiting to copy its place now wait for the user. */
export function removeItem(trip: Trip, date: string, itemId: string): Trip {
  return editDay(trip, date, (day) =>
    withItems(
      day,
      day.items
        .filter((it) => it.id !== itemId)
        .map((it) => (it.placeFrom?.id === itemId ? { ...it, placeFrom: null } : it)),
    ),
  )
}

function editDay(trip: Trip, date: string, f: (day: TripDay) => TripDay): Trip {
  return { ...trip, days: trip.days.map((d) => (d.date === date ? f(d) : d)) }
}

/** Timed items by start time; an item without a time keeps its position (there is nothing to sort
 *  it by). Array.sort is stable, so equal starts keep their order. */
function inTimeOrder(items: TripItem[]): TripItem[] {
  const timed = items.filter((it) => it.start != null).sort((a, b) => a.start! - b.start!)
  let next = 0
  return items.map((it) => (it.start == null ? it : timed[next++]))
}

/** The day with a new item list. The parser's issues name items by position, so each one follows
 *  its item to the new position, and an issue about a removed item goes. */
function withItems(day: TripDay, items: TripItem[]): TripDay {
  const position = new Map(items.map((it, i) => [it.id, i]))
  const issues = day.issues.flatMap((issue) => {
    const id = day.items[issue.item]?.id
    const at = id === undefined ? undefined : position.get(id)
    return at === undefined ? [] : [{ ...issue, item: at }]
  })
  return { ...day, items, issues }
}
