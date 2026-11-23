// A1 (review 2026-11-19): recovering in the middle of the day must not treat the places already
// visited as dropped. Sample = scenario A (Tokyo): meiji 09:20–10:20, harajuku 10:30–11:30,
// omotesando 11:40–12:40, ramen 12:50–13:50, ...
import { describe, expect, it } from 'vitest'
import type { DisruptionEvent } from '../api/types'
import {
  defaultVisited,
  holeEvent,
  holeLocation,
  inputFor,
  nextActivity,
  samplePlan,
  visitLocked,
  whereNow,
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

// withoutVisited / forEngine moved to the server: backend/tests/services/test_visited.py.

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


describe('inputFor', () => {
  it('sends the whole day with the ticked ids: the server takes them out', () => {
    const plan = samplePlan()
    const inp = inputFor(plan, rainAtNoon, ['meiji', 'harajuku'])
    expect(inp.visited).toEqual(['meiji', 'harajuku'])
    expect(inp.activities).toHaveLength(plan.activities.length)
  })
})

describe('whereNow', () => {
  it('is out on the day once a piece has started, not still at the hotel', () => {
    // Found 2026-11-23: at 17:00 the default was the hotel, so "늦어졌어요" read as "overslept",
    // nothing was pre-checked and the patch dropped the morning's visited places.
    expect(whereNow(samplePlan(), 17 * 60)).not.toBe('hotel')
    expect(whereNow(samplePlan(), NOON)).toBe('omotesando') // 11:40–12:40, in it
  })
  it('is the day start before the first piece', () => {
    expect(whereNow(samplePlan(), 8 * 60)).toBe('hotel')
  })
})
