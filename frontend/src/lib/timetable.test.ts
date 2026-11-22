// A3 (review 2026-11-19): the diff list followed the original order, so times read
// 13:20 -> 16:55 -> 15:00. It now reads in time order and marks what changed places.
import { describe, expect, it } from 'vitest'
import type { RecoveryChange } from '../api/types'
import { timetable } from './timetable'

const ch = (id: string, before: [number, number], after: [number, number] | null): RecoveryChange =>
  ({
    activity_id: id,
    op: after === null ? 'drop' : after[0] === before[0] ? 'keep' : 'move',
    before: { start: before[0], end: before[1] },
    after: after && { start: after[0], end: after[1] },
  }) as RecoveryChange

describe('timetable', () => {
  it('lists pieces by their new start; a dropped one stays at its planned time', () => {
    const rows = timetable([
      ch('shop', [800, 860], [800, 860]),
      ch('lunch', [780, 840], [1015, 1075]),
      ch('sky', [900, 960], [900, 960]),
      ch('cafe', [870, 890], null),
    ])
    expect(rows.map((r) => r.change.activity_id)).toEqual(['shop', 'cafe', 'sky', 'lunch'])
  })

  it('marks only the piece that moved further in a swapped pair', () => {
    const rows = timetable([
      ch('lunch', [780, 840], [1015, 1075]), // moved 235 min, now after sky
      ch('sky', [900, 960], [900, 960]), // reserved, did not move
    ])
    expect(rows.filter((r) => r.reordered).map((r) => r.change.activity_id)).toEqual(['lunch'])
  })

  it('marks both when they moved the same amount', () => {
    const rows = timetable([ch('a', [600, 660], [700, 760]), ch('b', [700, 760], [600, 660])])
    expect(rows.filter((r) => r.reordered).map((r) => r.change.activity_id)).toEqual(['b', 'a'])
  })

  it('marks nothing when the order is unchanged, however far things moved', () => {
    const rows = timetable([ch('a', [600, 660], [690, 750]), ch('b', [700, 760], [790, 850])])
    expect(rows.some((r) => r.reordered)).toBe(false)
  })

  it('is stable on equal times (original start, then id)', () => {
    const rows = timetable([ch('b', [600, 660], [700, 760]), ch('a', [650, 700], [700, 760])])
    expect(rows.map((r) => r.change.activity_id)).toEqual(['b', 'a'])
  })
})
