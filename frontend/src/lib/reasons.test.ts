// A4 (review 2026-11-19): the "past" reason was wrong for a delay, and "고정" was offered where it
// can only fail.
import { describe, expect, it } from 'vitest'
import type { DisruptionEvent, RecoveryChange } from '../api/types'
import { canLock, describeReason } from './reasons'

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

describe('describeReason', () => {
  it('says when the user can move again for a delay, not that the time has passed', () => {
    expect(describeReason(forced('move', 'past'), lateStart)).toBe('10:50까지 움직일 수 없어서 원래 시각에 갈 수 없었어요')
  })

  it('keeps "already passed" for other events', () => {
    expect(describeReason(forced('move', 'past'), rain)).toBe('원래 시각이 이미 지나서 그대로 둘 수 없었어요')
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
})
