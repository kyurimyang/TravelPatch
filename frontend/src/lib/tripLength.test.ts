import { describe, expect, it } from 'vitest'
import { tripLength } from './time'

describe('tripLength', () => {
  it('a one-day trip is 당일치기, not "0박 1일"', () => {
    expect(tripLength('2026-12-05', '2026-12-05')).toBe('당일치기')
    expect(tripLength('2026-10-07', '2026-10-09')).toBe('2박 3일')
  })
})
