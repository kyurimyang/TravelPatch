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

/**
 * Parsed draft -> the trip the app keeps. Day i of the text becomes startDate + i, in the order
 * written (the parser never reorders). Places start unpicked: the user confirms them on Confirm.
 * Tier default until the LLM step exists: reserved -> must, else nice (decisions 2026-11-17).
 */
export function tripFromDraft(draft: DraftItinerary, meta: TripMeta): Trip {
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
        placeId: null,
        tier: defaultTier({ reservationTime: it.reservation_time ?? null }),
      })),
    })),
  }
}
