import { describe, expect, it } from 'vitest'
import type { TravelTime } from '../api/types'
import { legsAlong, legIntoEach } from './legs'

const t = (a: string, b: string, minutes: number, source: 'api' | 'estimate' = 'estimate'): TravelTime => ({
  a,
  b,
  minutes,
  source,
})

describe('legsAlong', () => {
  const table = [t('a', 'b', 15, 'api'), t('b', 'c', 20), t('a', 'c', 40)]

  it('gives one leg between each neighbouring pair, in the order walked', () => {
    expect(legsAlong(['a', 'b', 'c'], table)).toEqual([
      { from: 'a', to: 'b', minutes: 15, source: 'api' },
      { from: 'b', to: 'c', minutes: 20, source: 'estimate' },
    ])
  })

  it('reads the table in both directions (it is undirected)', () => {
    expect(legsAlong(['c', 'b'], table)).toEqual([{ from: 'c', to: 'b', minutes: 20, source: 'estimate' }])
  })

  it('follows the given order, not the table order (a recovered day may reorder pieces)', () => {
    expect(legsAlong(['c', 'a'], table)[0]).toMatchObject({ from: 'c', to: 'a', minutes: 40 })
  })

  it('leaves a leg out when the table has no such pair, never inventing minutes', () => {
    expect(legsAlong(['a', 'z'], table)).toEqual([])
  })

  it('needs two stops for a leg', () => {
    expect(legsAlong([], table)).toEqual([])
    expect(legsAlong(['a'], table)).toEqual([])
  })
})

describe('legIntoEach', () => {
  const table = [t('a', 'b', 15, 'api'), t('b', 'c', 20)]

  it('keys each leg by the stop it arrives at, so a row can show the way into it', () => {
    const into = legIntoEach(['a', 'b', 'c'], table)
    expect(into.get('b')).toMatchObject({ from: 'a', minutes: 15 })
    expect(into.get('c')).toMatchObject({ from: 'b', minutes: 20 })
    expect(into.has('a')).toBe(false) // nothing arrives at the first stop
  })
})
