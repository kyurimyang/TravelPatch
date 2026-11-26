// "Today" and "now" come from the device: a traveller's phone is on local time at the destination.
// No GPS (decision 2026-11-17): where the user is comes from the user, never from here.
import type { Trip, TripDay, TripItem } from '../store/trip'

export function deviceNow(): { date: string; minutes: number } {
  const d = new Date()
  const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return { date, minutes: d.getHours() * 60 + d.getMinutes() }
}

/** First item not finished yet on the day being travelled; on any other day, the first item. */
export function nextItem(day: TripDay, isToday: boolean, now: number): TripItem | undefined {
  const timed = day.items.filter((it) => it.start != null && !it.dropped)
  return isToday ? timed.find((it) => (it.end ?? it.start!) > now) : timed[0]
}

export type TripPhase = 'ongoing' | 'upcoming' | 'past'

export function tripPhase(trip: Pick<Trip, 'startDate' | 'endDate'>, today: string): TripPhase {
  if (today < trip.startDate) return 'upcoming'
  if (today > trip.endDate) return 'past'
  return 'ongoing'
}

/** Items the user still has to settle (place not picked, or no usable time). Days before `today`
 *  are not counted: they cannot be edited any more (lib/tripEdit), so there is nothing to do. */
export function needsCheck(trip: Pick<Trip, 'days'>, today: string): number {
  return trip.days
    .filter((d) => d.date >= today)
    .flatMap((d) => d.items)
    .filter((it) => !it.dropped && (!it.placeId || it.start == null || it.end == null || it.end <= it.start)).length
}

/** The trip to open on "/" when none is chosen (a new device, the chosen one deleted): the one
 *  being travelled, else the next one coming, else the one that ended last. null: no trips. */
export function pickTrip<T extends Pick<Trip, 'id' | 'startDate' | 'endDate'>>(trips: T[], today: string): T | null {
  const ongoing = trips.filter((t) => tripPhase(t, today) === 'ongoing')
  if (ongoing.length) return ongoing.reduce((a, b) => (b.startDate > a.startDate ? b : a))
  const upcoming = trips.filter((t) => tripPhase(t, today) === 'upcoming')
  if (upcoming.length) return upcoming.reduce((a, b) => (b.startDate < a.startDate ? b : a))
  return trips.length ? trips.reduce((a, b) => (b.endDate > a.endDate ? b : a)) : null
}
