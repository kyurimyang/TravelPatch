import { describe, expect, it } from 'vitest'
import type { Trip, TripItem } from '../store/trip'
import { applyPatch, type SavedPatch } from './patches'
import { dayKept, tripKept } from './kept'

const item = (id: string, start: number, end: number, tier: TripItem['tier'] = 'nice'): TripItem => ({
  id, title: id, category: 'sightseeing', start, end, durationEstimated: false, reservationTime: null, note: null, placeId: id, tier,
})
const trip = (): Trip => ({
  id: 't', city: '도쿄', startDate: '2026-11-22', endDate: '2026-11-24', hotel: null, travelMode: 'transit', endDeadline: 1320,
  arrival: null, departure: null, patches: [],
  days: [
    { date: '2026-11-22', label: null, issues: [], items: [item('a', 600, 660), item('b', 700, 760)] },
    { date: '2026-11-23', label: null, issues: [], items: [item('c', 600, 720, 'must'), item('d', 780, 840), item('e', 900, 960)] },
    { date: '2026-11-24', label: null, issues: [], items: [item('f', 600, 660)] },
  ],
})
const patch = (id: string, changes: SavedPatch['changes']): SavedPatch => ({
  id, date: '2026-11-23', savedAt: '', strategy: 'balanced', preservationRate: 0.99, chips: [], eventType: 'DELAY', changes,
})

describe('dayKept', () => {
  it('counts against the original plan across two patches', () => {
    let t = applyPatch(trip(), patch('p1', [{ itemId: 'c', op: 'shrink', before: { start: 600, end: 720 }, after: { start: 600, end: 660 } }]))
    t = applyPatch(t, patch('p2', [{ itemId: 'd', op: 'drop', before: { start: 780, end: 840 }, after: null }]))
    // c: must (5) at half its length, d: nice (3) dropped, e: nice (3) kept -> (2.5 + 0 + 3) / 11
    expect(dayKept(t, '2026-11-23')).toBeCloseTo(5.5 / 11)
    // not the 99% the last patch said about the day it saw
  })
  it('is 1 for an untouched day', () => {
    expect(dayKept(trip(), '2026-11-22')).toBe(1)
  })
})

describe('tripKept', () => {
  it('leaves out days not reached yet', () => {
    const t = applyPatch(trip(), patch('p', [{ itemId: 'e', op: 'drop', before: { start: 900, end: 960 }, after: null }]))
    // days 1-2 only: (6 + 8) / 17; day 3 (future) is not a free 100%
    expect(tripKept(t, '2026-11-23')).toBeCloseTo(14 / 17)
  })
})
