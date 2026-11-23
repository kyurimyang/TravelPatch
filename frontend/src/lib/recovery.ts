// The day being recovered, shared by Recover -> DiffView -> NoPatch / Stitched through router state.
// It is built by the server from the trip (POST /plans/build) and kept in memory only: it holds
// Google coordinates, which the browser must not store (decision 2026-11-16).
import type { BuiltPlan, DisruptionEvent, PlanRequest, RecoveryInput, RecoveryRequest } from '../api/types'
import sample from '../mocks/scenarioAInput.json'
import type { Trip, TripFlight } from '../store/trip'

export type RecoverySource = 'trip' | 'sample'

export type RecoveryState = {
  plan: BuiltPlan
  source: RecoverySource
  event?: DisruptionEvent
  chips?: string[]
  /** Ticked as already visited on Recover; the server takes them out (decision 2026-11-22). */
  visited?: string[]
  /** MUST_VISIT: the Google place the user picked, so a stitched patch can add it to the trip. */
  addedPlaceId?: string
}

/** Scenario A (Tokyo), with coordinates and travel times inside: works offline, for demos. */
export function samplePlan(): BuiltPlan {
  const { day, activities, preferences, travel } = sample as unknown as RecoveryInput
  return { day, activities, preferences, travel, warnings: [] }
}

export function inputFor(plan: BuiltPlan, event: DisruptionEvent, visited: string[] = []): RecoveryRequest & RecoveryInput {
  // No substitutes: for a closure the server searches them itself (POST /recoveries). The visited
  // places stay in: the server removes them (services/visited.py, one rule for app and eval).
  return {
    visited,
    day: plan.day,
    activities: plan.activities,
    preferences: plan.preferences,
    travel: plan.travel,
    event,
    substitutes: [],
  }
}

// Same ids as backend HOTEL_ID / START_ID (the arrival airport).
export const HOTEL_ID = 'hotel'
export const START_ID = 'start'
const DAY_START_IDS = new Set([HOTEL_ID, START_ID])

/** The piece the user is late for or in: the first one not over by now. Not "the first starting
 * after now", which skips a piece that should have started already (A2). */
export function nextActivity<A extends { planned_end: number }>(activities: A[], now: number): A | undefined {
  return activities.find((a) => a.planned_end > now)
}

/** Where the plan says the user is at `now`: the last piece already started (in it, or just
 * left it), else the day's start. At 17:00 the user is out on the day, not still at the hotel;
 * the old default (always the hotel) made "늦어졌어요" read as "overslept" and left the
 * morning's pieces unchecked, so the patch dropped places already visited. */
export function whereNow(plan: BuiltPlan, now: number): string {
  const started = plan.activities.filter((a) => a.planned_start <= now)
  if (started.length > 0) return started.reduce((a, b) => (b.planned_start >= a.planned_start ? b : a)).id
  return plan.day.start_lat != null ? START_ID : HOTEL_ID
}

/** Where the user most likely is when the alert says a piece is late: the piece planned before it,
 * or the day's start when it is the first. The user can change it on Recover. */
export function holeLocation(plan: BuiltPlan, lateId: string): string {
  const i = plan.activities.findIndex((a) => a.id === lateId)
  if (i > 0) return plan.activities[i - 1].id
  return plan.day.start_lat != null ? START_ID : HOTEL_ID
}

/** The event for the hole alert, built without the LLM (decision 2026-11-19, A2): the alert knows
 * the facts already, and the lateness is inside `now`, so the user moves again from now. */
export function holeEvent(now: number, locationId: string): DisruptionEvent {
  return { type: 'DELAY', occurred_at: now, start_time: now, location_id: locationId }
}

/** Activities that cannot be marked visited: the one the event is about (the event refers to it).
 * Where the user is can be: the server keeps its place as the start node. */
export function visitLocked(event: DisruptionEvent): Set<string> {
  const target = 'activity_id' in event ? event.activity_id : null
  return new Set(target ? [target] : [])
}

/** Pre-checked as already visited (decision 2026-11-19, A1): planned to end by now. Nothing for a
 * delay, since the user has not left yet. The user unchecks what is wrong. In planned order. */
export function defaultVisited(plan: BuiltPlan, event: DisruptionEvent): string[] {
  // Still at the day's start (overslept, late departure): nothing visited yet. A delay out on the
  // day (the hole alert) pre-checks as usual.
  if (event.type === 'DELAY' && DAY_START_IDS.has(event.location_id ?? HOTEL_ID)) return []
  const locked = visitLocked(event)
  return plan.activities
    .filter((a) => a.planned_end <= event.occurred_at && !locked.has(a.id))
    .map((a) => a.id)
}

/** Names by id for activities and (when the server added them) substitutes. */
export function titlesOf(inp: Pick<RecoveryInput, 'activities' | 'substitutes'> & { event?: DisruptionEvent }): Map<string, string> {
  const added = inp.event?.type === 'MUST_VISIT' ? [[inp.event.activity_id, inp.event.title] as const] : []
  return new Map([
    ...inp.activities.map((a) => [a.id, a.title] as const),
    ...(inp.substitutes ?? []).map((s) => [s.id, s.title] as const),
    ...added,
  ])
}

const flight = (f: TripFlight | null) =>
  f ? { time: f.time, airport_place_id: f.airport.placeId, buffer_minutes: f.bufferMinutes } : null

/** The trip day as the server wants it, or why it cannot be sent yet. */
/** Most pieces one day may send to the server (backend MAX_ACTIVITIES). */
export const MAX_DAY_ITEMS = 16

export function planRequestFor(trip: Trip, dayIndex: number): PlanRequest | { problem: string } {
  const day = trip.days[dayIndex]
  const items = day?.items.filter((it) => !it.dropped) ?? []
  if (items.length === 0) return { problem: '이날에는 남은 일정이 없어요.' }
  // Same cap as the server (backend schemas/models.py MAX_ACTIVITIES): say it here, not as a 422.
  if (items.length > MAX_DAY_ITEMS) {
    return { problem: `하루에 조각이 ${MAX_DAY_ITEMS}개를 넘으면 패치를 찾을 수 없어요. 빼도 되는 조각을 '빼기'로 정리해 주세요.` }
  }
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
