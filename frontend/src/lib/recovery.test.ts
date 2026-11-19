// A1 (review 2026-11-19): recovering in the middle of the day must not treat the places already
// visited as dropped. Sample = scenario A (Tokyo): meiji 09:20–10:20, harajuku 10:30–11:30,
// omotesando 11:40–12:40, ramen 12:50–13:50, ...
import { describe, expect, it } from 'vitest'
import type { DisruptionEvent } from '../api/types'
import {
  defaultVisited,
  forEngine,
  holeEvent,
  holeLocation,
  inputFor,
  nextActivity,
  samplePlan,
  visitLocked,
  withoutVisited,
} from './recovery'

const NOON = 12 * 60
const rainAtNoon: DisruptionEvent = { type: 'WEATHER', occurred_at: NOON, start_time: NOON, location_id: 'omotesando' }

describe('defaultVisited', () => {
  it('pre-checks what ended before now, not what is in progress', () => {
    expect(defaultVisited(samplePlan(), rainAtNoon)).toEqual(['meiji', 'harajuku'])
  })

  it('pre-checks nothing for a delay at the hotel: the user has not left yet', () => {
    const overslept: DisruptionEvent = { type: 'DELAY', occurred_at: NOON, start_time: NOON + 60, location_id: 'hotel' }
    expect(defaultVisited(samplePlan(), overslept)).toEqual([])
  })

  it('pre-checks as usual for a delay out on the day (A2: a late hole from the alert)', () => {
    const late: DisruptionEvent = { type: 'DELAY', occurred_at: NOON, start_time: NOON, location_id: 'omotesando' }
    expect(defaultVisited(samplePlan(), late)).toEqual(['meiji', 'harajuku'])
  })

  it('pre-checks where the user is when it is over: they are about to leave it', () => {
    const atHarajuku: DisruptionEvent = { ...rainAtNoon, location_id: 'harajuku' }
    expect(defaultVisited(samplePlan(), atHarajuku)).toEqual(['meiji', 'harajuku'])
  })

  it('never pre-checks what the event is about', () => {
    const meijiClosed: DisruptionEvent = { type: 'CLOSURE', occurred_at: NOON, activity_id: 'meiji', location_id: 'omotesando' }
    expect(defaultVisited(samplePlan(), meijiClosed)).toEqual(['harajuku'])
  })
})

describe('visitLocked', () => {
  it('is only the event target: the event refers to it', () => {
    const ev: DisruptionEvent = { type: 'EXTEND', occurred_at: NOON, activity_id: 'ramen', extra_minutes: 30, location_id: 'omotesando' }
    expect([...visitLocked(ev)]).toEqual(['ramen'])
  })
})

// Visited and still standing there: over, but the place is where the rest of the day starts from.
// Kept as an activity, the engine reads it as under way and drops it (it ended before now).
describe('forEngine', () => {
  const atHarajuku: DisruptionEvent = { type: 'DELAY', occurred_at: NOON + 8, start_time: NOON + 8, location_id: 'harajuku' }

  it('turns a visited current place into the start node', () => {
    const plan = samplePlan()
    const harajuku = plan.activities.find((a) => a.id === 'harajuku')!
    const out = forEngine(plan, atHarajuku, ['meiji', 'harajuku'])
    expect(out.event.location_id).toBe('start')
    expect(out.plan.activities.map((a) => a.id)).not.toContain('harajuku')
    expect([out.plan.day.start_lat, out.plan.day.start_lng]).toEqual([harajuku.lat, harajuku.lng])
    const minutes = (a: string, b: string, travel = plan.travel) =>
      travel.find((t) => (t.a === a && t.b === b) || (t.a === b && t.b === a))?.minutes
    expect(minutes('start', 'omotesando', out.plan.travel)).toBe(minutes('harajuku', 'omotesando'))
    expect(minutes('start', 'hotel', out.plan.travel)).toBe(minutes('harajuku', 'hotel'))
    // 6 activities + hotel + start = 8 nodes = 28 pairs.
    expect(out.plan.travel).toHaveLength(28)
  })

  it('replaces an arrival airport start: by now the day starts from where the user is', () => {
    const base = samplePlan()
    const nodes = ['hotel', ...base.activities.map((a) => a.id)]
    const plan = {
      ...base,
      day: { ...base.day, start_lat: 35.55, start_lng: 139.78 },
      travel: [...base.travel, ...nodes.map((n) => ({ a: 'start', b: n, minutes: 99, source: 'estimate' as const }))],
    }
    const out = forEngine(plan, atHarajuku, ['meiji', 'harajuku'])
    expect(out.plan.travel.some((t) => t.minutes === 99)).toBe(false)
    expect(out.plan.travel).toHaveLength(28)
  })

  it('leaves the event alone when the current place is not checked (still under way)', () => {
    const out = forEngine(samplePlan(), atHarajuku, ['meiji'])
    expect(out.event).toEqual(atHarajuku)
    expect(out.plan.activities.map((a) => a.id)).toContain('harajuku')
    expect(out.plan.day.start_lat ?? null).toBeNull()
  })
})

describe('withoutVisited', () => {
  it('removes visited places from activities, preferences and every travel pair', () => {
    const plan = withoutVisited(samplePlan(), ['meiji', 'harajuku'])
    const gone = new Set(['meiji', 'harajuku'])
    expect(plan.activities.map((a) => a.id)).not.toContain('meiji')
    expect(plan.activities.map((a) => a.id)).not.toContain('harajuku')
    expect(plan.preferences.some((p) => gone.has(p.activity_id))).toBe(false)
    expect(plan.travel.some((t) => gone.has(t.a) || gone.has(t.b))).toBe(false)
    // 8 activities + hotel = 36 pairs; 6 + hotel = 21 pairs (the engine checks the table is complete).
    expect(plan.travel).toHaveLength(21)
  })

  it('keeps the plan as it was when nothing is checked', () => {
    expect(withoutVisited(samplePlan(), [])).toEqual(samplePlan())
  })
})

// A2 (review 2026-11-19): the alert said "18 minutes late" and Recover added 18 minutes on top of
// a "now" that already contained them; it also showed lunch, not the late piece, as "next".
describe('hole alert', () => {
  it('moves from now: the lateness is already inside now, nothing is added', () => {
    expect(holeEvent(NOON + 8, 'harajuku')).toEqual({
      type: 'DELAY',
      occurred_at: NOON + 8,
      start_time: NOON + 8,
      location_id: 'harajuku',
    })
  })

  it('starts from the piece before the late one, or the hotel for the first', () => {
    expect(holeLocation(samplePlan(), 'omotesando')).toBe('harajuku')
    expect(holeLocation(samplePlan(), 'meiji')).toBe('hotel')
  })
})

describe('nextActivity', () => {
  it('is the piece still under way, not the first one starting after now', () => {
    // 12:00: omotesando (11:40–12:40) is late or under way; lunch starts 12:50.
    expect(nextActivity(samplePlan().activities, NOON)?.id).toBe('omotesando')
    expect(nextActivity(samplePlan().activities, 12 * 60 + 45)?.id).toBe('ramen')
  })
})

describe('noon recovery input', () => {
  it('does not send the morning places to the engine', () => {
    const plan = samplePlan()
    const inp = inputFor(withoutVisited(plan, defaultVisited(plan, rainAtNoon)), rainAtNoon)
    expect(inp.activities.map((a) => a.id)).toEqual([
      'omotesando',
      'ramen',
      'shibuya_shop',
      'cafe',
      'sky',
      'izakaya',
    ])
  })
})
