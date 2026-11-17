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

/** Items the user still has to settle on Confirm (place not picked, or no usable time). */
export function needsCheck(trip: Trip): number {
  return trip.days
    .flatMap((d) => d.items)
    .filter((it) => !it.dropped && (!it.placeId || it.start == null || it.end == null || it.end <= it.start)).length
}
