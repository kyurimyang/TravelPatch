import { describe, expect, it } from 'vitest'
import type { RecoveryChange } from '../api/types'
import { shiftLabel, shiftSentence, timeShift } from './shift'

const slot = (start: number, end: number) => ({ start, end })
const ch = (op: RecoveryChange['op'], before: [number, number], after?: [number, number]) =>
  ({ activity_id: 'x', op, before: slot(...before), after: after ? slot(...after) : null }) as RecoveryChange

describe('timeShift', () => {
  it('averages the moved pieces only', () => {
    const s = timeShift({ changes: [ch('keep', [600, 660], [600, 660]), ch('move', [700, 760], [760, 820]), ch('move', [800, 860], [820, 880])] })
    expect(s).toEqual({ moved: 2, avgMinutes: 40 })
    expect(shiftLabel(s)).toBe('평균 40분 늦춤')
  })
  it('leaves out drops and substitutes', () => {
    expect(timeShift({ changes: [ch('drop', [600, 660]), ch('substitute', [700, 760], [900, 960])] })).toBeNull()
  })
  it('says earlier, and hours', () => {
    expect(shiftLabel({ moved: 1, avgMinutes: -15 })).toBe('평균 15분 당김')
    expect(shiftLabel({ moved: 3, avgMinutes: 95 })).toBe('평균 1시간 35분 늦춤')
    expect(shiftLabel({ moved: 3, avgMinutes: 120 })).toBe('평균 2시간 늦춤')
  })
})

describe('shiftSentence', () => {
  it('reads as a sentence', () => {
    expect(shiftSentence({ moved: 3, avgMinutes: 40 })).toBe('3곳의 시작이 평균 40분 늦춰졌어요.')
    expect(shiftSentence({ moved: 1, avgMinutes: -60 })).toBe('1곳의 시작이 평균 1시간 당겨졌어요.')
    expect(shiftSentence(null)).toBeNull()
  })
})
