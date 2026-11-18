// The day being recovered, shared by Recover -> DiffView -> NoPatch / Stitched through router state.
// It is built by the server from the trip (POST /plans/build) and kept in memory only: it holds
// Google coordinates, which the browser must not store (decision 2026-11-16).
import type { BuiltPlan, DisruptionEvent, PlanRequest, RecoveryInput } from '../api/types'
import sample from '../mocks/scenarioAInput.json'
import type { Trip, TripFlight } from '../store/trip'

export type RecoverySource = 'trip' | 'sample'

export type RecoveryState = {
  plan: BuiltPlan
  source: RecoverySource
  event?: DisruptionEvent
  chips?: string[]
}

/** Scenario A (Tokyo), with coordinates and travel times inside: works offline, for demos. */
export function samplePlan(): BuiltPlan {
  const { day, activities, preferences, travel } = sample as unknown as RecoveryInput
  return { day, activities, preferences, travel, warnings: [] }
}

export function inputFor(plan: BuiltPlan, event: DisruptionEvent): RecoveryInput {
  // No substitutes: for a closure the server searches them itself (POST /recoveries).
  return {
    day: plan.day,
    activities: plan.activities,
    preferences: plan.preferences,
    travel: plan.travel,
    event,
    substitutes: [],
  }
}

/** Names by id for activities and (when the server added them) substitutes. */
export function titlesOf(inp: Pick<RecoveryInput, 'activities' | 'substitutes'>): Map<string, string> {
  return new Map([
    ...inp.activities.map((a) => [a.id, a.title] as const),
    ...(inp.substitutes ?? []).map((s) => [s.id, s.title] as const),
  ])
}

const flight = (f: TripFlight | null) =>
  f ? { time: f.time, airport_place_id: f.airport.placeId, buffer_minutes: f.bufferMinutes } : null

/** The trip day as the server wants it, or why it cannot be sent yet. */
export function planRequestFor(trip: Trip, dayIndex: number): PlanRequest | { problem: string } {
  const day = trip.days[dayIndex]
  const items = day?.items.filter((it) => !it.dropped) ?? []
  if (items.length === 0) return { problem: '이날에는 남은 일정이 없어요.' }
  if (!trip.hotel) return { problem: '숙소가 정해지지 않았어요.' }
  const notReady = items.filter((it) => !it.placeId || it.start == null || it.end == null || it.end <= it.start)
  if (notReady.length > 0) {
    return { problem: `장소나 시각을 확인하지 않은 조각이 ${notReady.length}개 있어요. 일정 확인에서 마저 정해 주세요.` }
  }
  return {
    date: day.date,
    hotel_place_id: trip.hotel.placeId,
    // The arrival flight bounds the first day, the departure flight the last one; a departure
    // replaces the back-at-hotel deadline on its day (the server accepts one or the other).
    arrival: day.date === trip.startDate ? flight(trip.arrival) : null,
    departure: day.date === trip.endDate ? flight(trip.departure) : null,
    end_deadline: day.date === trip.endDate && trip.departure ? null : trip.endDeadline,
    travel_mode: trip.travelMode,
    items: items.map((it) => ({
      id: it.id,
      title: it.title,
      category: it.category,
      start: it.start!,
      end: it.end!,
      place_id: it.placeId!,
      tier: it.tier,
      reservation_time: it.reservationTime,
    })),
  }
}
