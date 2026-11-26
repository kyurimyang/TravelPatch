import { describe, expect, it } from 'vitest'
import type { Counterfactual, RecoveryChange } from '../api/types'
import { tradeoffs } from './tradeoff'

const ch = (id: string, op: RecoveryChange['op'], after: [number, number] | null, sub?: string): RecoveryChange =>
  ({
    activity_id: id,
    op,
    before: { start: 600, end: 660 },
    after: after && { start: after[0], end: after[1] },
    substitute_id: sub ?? null,
    needs_check: false,
  }) as unknown as RecoveryChange

const cf = (...pairs: [string, RecoveryChange, RecoveryChange][]): Counterfactual =>
  ({
    restored_id: 'harajuku',
    d_preservation: 0,
    d_rc: 0,
    result: {},
    side_effects: pairs.map(([id, before, after]) => ({ activity_id: id, before, after })),
  }) as unknown as Counterfactual

const names: Record<string, string> = { meiji: '메이지 신궁', ramen: '라멘 점심', shop: '시부야 쇼핑', cafe: '카페', sub1: '실내 전시', sub2: '근처 미술관' }
const titleOf = (id: string) => names[id] ?? id

describe('tradeoffs', () => {
  it('the screenshot case: only the real loss is left', () => {
    const out = tradeoffs(
      cf(
        ['meiji', ch('meiji', 'substitute', [600, 660], 'sub1'), ch('meiji', 'substitute', [600, 660], 'sub1')],
        ['ramen', ch('ramen', 'move', [700, 760]), ch('ramen', 'keep', [600, 660])],
        ['shop', ch('shop', 'move', [800, 890]), ch('shop', 'shrink', [800, 850])],
      ),
      titleOf,
    )
    expect(out).toEqual(['시부야 쇼핑 −40분'])
  })

  it('worst first: a drop, then a swap, a cut, a move', () => {
    const out = tradeoffs(
      cf(
        ['ramen', ch('ramen', 'keep', [600, 660]), ch('ramen', 'move', [620, 680])],
        ['shop', ch('shop', 'keep', [600, 660]), ch('shop', 'shrink', [600, 630])],
        ['meiji', ch('meiji', 'keep', [600, 660]), ch('meiji', 'substitute', [600, 660], 'sub2')],
        ['cafe', ch('cafe', 'keep', [600, 660]), ch('cafe', 'drop', null)],
      ),
      titleOf,
      4,
    )
    expect(out).toEqual(['카페 빠짐', '메이지 신궁 → 근처 미술관', '시부야 쇼핑 −30분', '라멘 점심 10:20부터'])
  })

  it('a piece brought back or lengthened is not a loss', () => {
    expect(tradeoffs(cf(['cafe', ch('cafe', 'drop', null), ch('cafe', 'keep', [600, 660])]), titleOf)).toEqual([])
  })

  it('counts what does not fit', () => {
    const many = ['a', 'b', 'c', 'd', 'e'].map(
      (id) => [id, ch(id, 'keep', [600, 660]), ch(id, 'drop', null)] as [string, RecoveryChange, RecoveryChange],
    )
    expect(tradeoffs(cf(...many), titleOf)).toEqual(['a 빠짐', 'b 빠짐', 'c 빠짐', '외 2곳'])
  })
})
