import type { DraftItinerary } from '../api/types'
import { DEFAULT_END_DEADLINE, type Trip, type TripItem } from '../store/trip'
import { defaultTier } from './category'

type TripMeta = Pick<Trip, 'city' | 'startDate' | 'endDate' | 'hotel' | 'travelMode' | 'arrival' | 'departure'>
type DraftDay = DraftItinerary['days'][number]
type DraftItem = DraftDay['items'][number]

/** ISO date `days` after `iso` ("2026-10-08" + 1 -> "2026-10-09"). UTC math: no DST surprises. */
export function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

/**
 * Where an item is, from the server's place rules (decision 2026-11-23). Nothing is ever searched
 * by the title: an item with no written place is left for the user to pick.
 * - hotel: the registered hotel at once. An airport item on the first/last day: the flight's airport.
 * - written: search the name with the address, when one is written (the surest match).
 * - venue / previous with `place_of`: copy that item's place on Confirm (one pin per theme park).
 * - venue without it: search the larger place's name.
 */
function placeOf(it: DraftItem, di: number, dayCount: number, meta: TripMeta): Pick<TripItem, 'placeId' | 'placeQuery' | 'placeFrom'> {
  const none = { placeId: null, placeQuery: null, placeFrom: null }
  if (it.place_source === 'hotel') return { ...none, placeId: meta.hotel?.placeId ?? null }
  if (it.role === 'airport') {
    const flight = di === 0 ? meta.arrival : di === dayCount - 1 ? meta.departure : null
    if (flight) return { ...none, placeId: flight.airport.placeId }
  }
  if ((it.place_source === 'venue' || it.place_source === 'previous') && it.place_of != null) {
    return { ...none, placeFrom: { id: `d${di}-${it.place_of}`, why: it.place_source } }
  }
  const query = [it.place_query, it.address].filter(Boolean).join(' ')
  return { ...none, placeQuery: query || null }
}

/** The end time the text writes for the day at the hotel, when every day that writes one agrees. */
function writtenDeadline(days: DraftDay[]): number | null {
  const ends = new Set(days.map((d) => d.end_time).filter((m): m is number => m != null))
  return ends.size === 1 ? [...ends][0] : null
}

/**
 * Parsed draft -> the trip the app keeps. Day i of the text becomes startDate + i, in the order
 * written (the parser never reorders). Hotel items get their place here; the rest are searched or
 * copied on Confirm. Flights written in the text wait on Confirm for their airport, unless the
 * user entered them at registration. Tier default until the LLM step exists: reserved -> must,
 * else nice (decisions 2026-11-17).
 */
export function tripFromDraft(draft: DraftItinerary, meta: TripMeta): Trip {
  const dayCount = draft.days.length
  const first = draft.days[0]
  const last = draft.days[dayCount - 1]
  return {
    id: crypto.randomUUID(),
    ...meta,
    endDeadline: writtenDeadline(draft.days) ?? DEFAULT_END_DEADLINE,
    textFlights: {
      arrival: meta.arrival ? null : (first?.arrival ?? null),
      departure: meta.departure ? null : (last?.departure ?? null),
    },
    patches: [],
    days: draft.days.map((day, di) => ({
      date: addDays(meta.startDate, di),
      label: day.day_label ?? null,
      issues: day.issues ?? [],
      items: day.items.map((it, ii) => ({
        id: `d${di}-${ii}`,
        title: it.title,
        category: it.category,
        start: it.start ?? null,
        end: it.end ?? null,
        durationEstimated: it.duration_estimated ?? false,
        reservationTime: it.reservation_time ?? null,
        note: it.note ?? null,
        patch: it.patch ?? null,
        ...placeOf(it, di, dayCount, meta),
        tier: defaultTier({ reservationTime: it.reservation_time ?? null }),
      })),
    })),
  }
}
