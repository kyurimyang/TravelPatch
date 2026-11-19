import type { DraftItinerary } from '../api/types'
import { DEFAULT_END_DEADLINE, type Trip } from '../store/trip'
import { defaultTier } from './category'

type TripMeta = Pick<Trip, 'city' | 'startDate' | 'endDate' | 'hotel' | 'travelMode' | 'arrival' | 'departure'>

/** ISO date `days` after `iso` ("2026-10-08" + 1 -> "2026-10-09"). UTC math: no DST surprises. */
export function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

// Lines that are about the hotel or the airport, not a place to look up. Narrow on purpose:
// "호텔" alone is not enough ("파크 하얏트 뉴욕 바" is a bar to search for).
const HOTEL_LINE = /체크\s?인|체크\s?아웃|check[\s-]?in|check[\s-]?out|숙소|짐\s?(맡기|찾)|호텔\s?(복귀|귀환|도착|휴식)/i
const AIRPORT_LINE = /공항|airport|출국|입국|탑승|비행기/i

/**
 * The place already known for a line, so it is never searched (decision 2026-11-18): hotel lines
 * get the hotel, airport lines on the first/last day get the flight's airport. Otherwise null.
 */
function knownPlace(title: string, dayIndex: number, dayCount: number, meta: TripMeta): string | null {
  if (meta.hotel && HOTEL_LINE.test(title)) return meta.hotel.placeId
  if (AIRPORT_LINE.test(title)) {
    if (dayIndex === 0 && meta.arrival) return meta.arrival.airport.placeId
    if (dayIndex === dayCount - 1 && meta.departure) return meta.departure.airport.placeId
  }
  return null
}

/**
 * Parsed draft -> the trip the app keeps. Day i of the text becomes startDate + i, in the order
 * written (the parser never reorders). Hotel and airport lines get their place here; the rest are
 * searched on Confirm. Tier default until the LLM step exists: reserved -> must, else nice
 * (decisions 2026-11-17).
 */
export function tripFromDraft(draft: DraftItinerary, meta: TripMeta): Trip {
  const dayCount = draft.days.length
  return {
    id: crypto.randomUUID(),
    ...meta,
    endDeadline: DEFAULT_END_DEADLINE,
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
        placeQuery: it.place_query ?? null,
        placeId: knownPlace(it.title, di, dayCount, meta),
        tier: defaultTier({ reservationTime: it.reservation_time ?? null }),
      })),
    })),
  }
}
