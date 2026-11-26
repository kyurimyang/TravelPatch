import { describe, expect, it } from 'vitest'
import type { Trip, TripItem } from '../store/trip'
import { applyPatch, type SavedPatch } from './patches'
import { addItem, changeTime, dayLock, removeItem, unpatchDay } from './tripEdit'

const DATE = '2026-11-28'
const item = (id: string, start: number | null, end: number | null, extra: Partial<TripItem> = {}): TripItem => ({
  id, title: id, category: 'sightseeing', start, end, durationEstimated: false, reservationTime: null, note: null, placeId: id, tier: 'nice', ...extra,
})
const trip = (items = [item('a', 600, 660), item('b', 780, 840), item('c', 900, 960)]): Trip => ({
  id: 't', city: '도쿄', startDate: DATE, endDate: '2026-11-29', hotel: null, travelMode: 'transit', endDeadline: 1320,
  arrival: null, departure: null, patches: [],
  days: [
    { date: DATE, label: null, issues: [], items },
    { date: '2026-11-29', label: null, issues: [], items: [item('z', 600, 660)] },
  ],
})
const patch = (id: string, changes: SavedPatch['changes'], date = DATE): SavedPatch => ({
  id, date, savedAt: '', strategy: 'balanced', preservationRate: 1, chips: [], eventType: 'DELAY', changes,
})
const ids = (t: Trip) => t.days[0].items.map((i) => i.id)

describe('dayLock', () => {
  const patched = applyPatch(trip(), patch('p1', [{ itemId: 'b', op: 'drop', before: { start: 780, end: 840 }, after: null }]))

  it('locks a past day, patched or not', () => {
    expect(dayLock(trip(), DATE, '2026-11-29')).toBe('past')
    expect(dayLock(patched, DATE, '2026-11-29')).toBe('past')
  })
  it('locks today and later days only while they carry a patch', () => {
    expect(dayLock(trip(), DATE, DATE)).toBeNull()
    expect(dayLock(patched, DATE, DATE)).toBe('patched')
    expect(dayLock(patched, '2026-11-29', DATE)).toBeNull()
  })
})

describe('unpatchDay', () => {
  it('takes every patch of the day off and gives back the plan before the first one', () => {
    const first = patch('p1', [
      { itemId: 'a', op: 'move', before: { start: 600, end: 660 }, after: { start: 630, end: 690 } },
      { itemId: 'b', op: 'drop', before: { start: 780, end: 840 }, after: null },
    ])
    const second = patch('p2', [
      { itemId: 'a', op: 'shrink', before: { start: 630, end: 690 }, after: { start: 640, end: 670 } },
      {
        itemId: 'x', op: 'add', before: null, after: { start: 700, end: 760 },
        added: { title: 'x', category: 'sightseeing', placeId: 'x' },
      },
    ])
    const other = patch('p3', [{ itemId: 'z', op: 'drop', before: { start: 600, end: 660 }, after: null }], '2026-11-29')
    const patched = [first, second, other].reduce(applyPatch, trip())

    const restored = unpatchDay(patched, DATE)

    expect(ids(restored)).toEqual(['a', 'b', 'c'])
    expect(restored.days[0].items[0]).toMatchObject({ start: 600, end: 660, patched: false })
    expect(restored.days[0].items[1]).toMatchObject({ dropped: false, patched: false })
    // The other day keeps its patch.
    expect(restored.patches.map((p) => p.id)).toEqual(['p3'])
    expect(restored.days[1].items[0].dropped).toBe(true)
  })
})

describe('changeTime', () => {
  it('re-sorts the day, and the parser issues follow their items', () => {
    const t = trip([item('a', 600, 660), item('b', null, null), item('c', 900, 960)])
    t.days[0].issues = [{ code: 'NO_TIME', item: 1, detail: '' }, { code: 'OVERLAP', item: 2, detail: '' }]
    const after = changeTime(t, DATE, 'c', { start: 480, end: 540, reservationTime: null })
    // b has no time: it stays in the middle; a and c swap around it.
    expect(ids(after)).toEqual(['c', 'b', 'a'])
    expect(after.days[0].issues.map((i) => [i.code, i.item])).toEqual([['NO_TIME', 1], ['OVERLAP', 0]])
  })
})

describe('addItem and removeItem', () => {
  it('adds in time order', () => {
    expect(ids(addItem(trip(), DATE, item('n', 700, 760)))).toEqual(['a', 'n', 'b', 'c'])
  })
  it('removes the item, its issues and the links to its place', () => {
    const t = trip([item('a', 600, 660), item('b', 780, 840, { placeId: null, placeFrom: { id: 'a', why: 'venue' } }), item('c', 900, 960)])
    t.days[0].issues = [{ code: 'OVERLAP', item: 0, detail: '' }, { code: 'OVERLAP', item: 2, detail: '' }]
    const after = removeItem(t, DATE, 'a')
    expect(ids(after)).toEqual(['b', 'c'])
    expect(after.days[0].items[0].placeFrom).toBeNull()
    expect(after.days[0].issues.map((i) => i.item)).toEqual([1])
  })
})
