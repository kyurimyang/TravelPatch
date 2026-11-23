import { describe, expect, it } from 'vitest'
import type { RecoveryResult } from '../api/types'
import type { Trip, TripItem } from '../store/trip'
import { applyPatch, patchFrom, undoPatch } from './patches'

const item = (id: string, start: number, end: number): TripItem => ({
  id, title: id, category: 'sightseeing', start, end, durationEstimated: false, reservationTime: null, note: null, placeId: id, tier: 'nice',
})
const trip = (): Trip => ({
  id: 't', city: '도쿄', startDate: '2026-11-23', endDate: '2026-11-23', hotel: null, travelMode: 'transit', endDeadline: 1320,
  arrival: null, departure: null, patches: [],
  days: [{ date: '2026-11-23', label: null, issues: [], items: [item('a', 600, 660), item('b', 780, 840)] }],
})
const result = {
  strategy: 'balanced', rc_total: 1, preservation_rate: 1, violations: 0, solver_ms: 1,
  rc_breakdown: { d_drop: 0, d_shrink: 0, d_sub: 0, d_order: 0, d_time: 0, d_move: 0, d_intent: 0, d_changed: 1 },
  changes: [
    { activity_id: 'a', op: 'keep', before: { start: 600, end: 660 }, after: { start: 600, end: 660 } },
    { activity_id: 'b', op: 'keep', before: { start: 780, end: 840 }, after: { start: 780, end: 840 } },
    { activity_id: 'add-x', op: 'add', before: null, after: { start: 690, end: 750 } },
  ],
} as unknown as RecoveryResult

describe('a MUST_VISIT patch', () => {
  it('adds the new place to the day as a must, in time order, and undo takes it out again', () => {
    const added = { title: '팀랩', category: 'sightseeing' as const, placeId: 'ChIJteamlab' }
    const patch = patchFrom('p1', '2026-11-23', result, [], '', 'MUST_VISIT', added)
    const after = applyPatch(trip(), patch)
    const items = after.days[0].items
    expect(items.map((i) => i.id)).toEqual(['a', 'add-x', 'b'])
    expect(items[1]).toMatchObject({ title: '팀랩', tier: 'must', start: 690, end: 750, placeId: 'ChIJteamlab', patched: true })
    expect(undoPatch(after, 'p1').days[0].items.map((i) => i.id)).toEqual(['a', 'b'])
  })
})
