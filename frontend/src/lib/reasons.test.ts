// A4 (review 2026-11-19): the "past" reason was wrong for a delay, and "고정" was offered where it
// can only fail.
import { describe, expect, it } from 'vitest'
import type { DisruptionEvent, RecoveryChange } from '../api/types'
import { canLock, reasonTag } from './reasons'

const forced = (op: RecoveryChange['op'], ...kinds: string[]): RecoveryChange =>
  ({
    activity_id: 'meiji',
    op,
    before: { start: 560, end: 620 },
    after: op === 'drop' ? null : { start: 650, end: 710 },
    reason_type: 'binding',
    reason_data: { forced_by: kinds },
  }) as unknown as RecoveryChange

const lateStart: DisruptionEvent = { type: 'DELAY', occurred_at: 530, start_time: 650, location_id: 'hotel' }
const rain: DisruptionEvent = { type: 'WEATHER', occurred_at: 720, start_time: 720, location_id: 'hotel' }

describe('reasonTag', () => {
  it('a delay says "늦어져서", not that the time has passed', () => {
    expect(reasonTag(forced('move', 'past'), lateStart)).toBe('늦어져서')
    expect(reasonTag(forced('move', 'past'), rain)).toBe('시간이 지나서')
  })

  it('names the first rule that forced it', () => {
    expect(reasonTag(forced('drop', 'weather', 'travel'), rain)).toBe('비 때문에')
  })

  it('a value choice names the tier', () => {
    const cut = { ...forced('drop'), reason_type: 'value', reason_data: { forced_by: [], value: 1 } } as RecoveryChange
    expect(reasonTag(cut)).toBe('‘선택’ 일정이라')
  })

  it('a piece an event names says so, with the event’s own number', () => {
    const queue: DisruptionEvent = { type: 'WAIT', occurred_at: 540, activity_id: 'meiji', minutes: 40, location_id: 'hotel' }
    expect(reasonTag(forced('extend', 'travel'), rain, [queue])).toBe('대기 40분 포함')
  })

  it('says nothing rather than a vague sentence when no single reason is known', () => {
    expect(reasonTag({ ...forced('move'), reason_type: null, reason_data: null } as unknown as RecoveryChange)).toBeNull()
  })
})

describe('canLock', () => {
  it('is false when the original slot breaks a rule of its own (always fails)', () => {
    for (const kind of ['past', 'closure', 'hours', 'weather', 'fatigue']) {
      expect(canLock(forced('move', kind))).toBe(false)
    }
  })

  it('is true when only other pieces are in the way', () => {
    expect(canLock(forced('move', 'travel'))).toBe(true)
    expect(canLock(forced('move', 'deadline'))).toBe(true)
    expect(canLock({ ...forced('shrink'), reason_type: 'value', reason_data: { forced_by: [] } } as RecoveryChange)).toBe(true)
  })

  it('is false for keep and drop (nothing to lock; a drop has "되살리면?")', () => {
    expect(canLock(forced('keep'))).toBe(false)
    expect(canLock(forced('drop', 'travel'))).toBe(false)
  })

  it('is false for the extension the user asked for (locking it would undo the ask)', () => {
    expect(canLock(forced('extend', 'travel'))).toBe(false)
  })
})
