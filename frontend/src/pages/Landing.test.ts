import { describe, expect, it } from 'vitest'
import { shortfall } from './Landing'

describe('shortfall', () => {
  it('says so when a 4-day trip came back as 1 day (the Prague paste, 2026-11-23)', () => {
    const lines = shortfall(1, '2026-12-01', '2026-12-04', { read: 10, written: 51 })
    expect(lines).toHaveLength(2)
    expect(lines[0]).toContain('51개 중 10개')
    expect(lines[1]).toContain('4일인데, 일정은 1일치')
  })
  it('names each time line it could not read (the Busan paste, 2026-11-28)', () => {
    const lines = shortfall(3, '2027-01-15', '2027-01-17', {
      read: 28,
      written: 29,
      missing: ['* 20:00~ · 숙소 이동 및 휴식'],
    })
    expect(lines).toEqual([
      expect.stringContaining('29개 중 28개'),
      '못 읽은 줄: * 20:00~ · 숙소 이동 및 휴식',
    ])
  })
  it('is empty for a complete read that matches the dates', () => {
    expect(shortfall(4, '2026-12-01', '2026-12-04', null)).toEqual([])
  })
  it('points at the dates when the text has more days', () => {
    expect(shortfall(4, '2026-12-01', '2026-12-02', null)[0]).toContain('오는 날을 확인')
  })
})
