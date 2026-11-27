import { describe, expect, it } from 'vitest'
import type { RecoveryResult } from '../api/types'
import { patchNote, tabLine } from './patchText'

const ch = (op: string, b: [number, number] | null, a: [number, number] | null) => ({
  activity_id: `${op}${b?.[0] ?? a?.[0]}`,
  op,
  before: b && { start: b[0], end: b[1] },
  after: a && { start: a[0], end: a[1] },
})
const r = (changes: ReturnType<typeof ch>[], rate = 0.96) =>
  ({ changes, preservation_rate: rate }) as unknown as RecoveryResult

describe('patch text', () => {
  const delayed = r([ch('keep', [540, 600], [540, 600]), ch('shrink', [620, 680], [660, 700]), ch('move', [700, 760], [750, 810])])
  it('says what a candidate gives up, in words, with no metrics', () => {
    expect(tabLine(delayed)).toBe('빼는 곳 없이 · 45분 밀림')
    expect(patchNote(delayed)).toEqual(['원래 계획 96% 그대로', '1곳은 짧게', '평균 45분 늦게'])
  })
  it('names drops and substitutes', () => {
    const dropped = r([ch('drop', [540, 600], null), ch('substitute', [620, 680], [620, 680])], 0.7)
    expect(tabLine(dropped)).toBe('1곳 빼고 · 1곳 근처로')
    expect(patchNote(dropped)).toEqual(['원래 계획 70% 그대로', '1곳은 오늘 빼요', '1곳은 근처 다른 곳으로'])
  })
  it('all kept but moved: says nothing was cut, not "100% 그대로" beside "2시간 늦게"', () => {
    const late = r([ch('move', [540, 600], [670, 730]), ch('move', [620, 680], [750, 810])], 1)
    expect(patchNote(late)).toEqual(['빼거나 줄인 곳 없어요', '평균 2시간 10분 늦게'])
    expect(patchNote(r([ch('keep', [540, 600], [540, 600])], 1))).toEqual(['원래 계획 100% 그대로'])
  })
  it('never mentions violations', () => {
    expect([tabLine(delayed), ...patchNote(delayed)].join(' ')).not.toMatch(/위반|보존율/)
  })
})
