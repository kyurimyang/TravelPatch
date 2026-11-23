import { describe, expect, it } from 'vitest'
import { pickTrip } from './today'

const t = (id: string, startDate: string, endDate: string) => ({ id, startDate, endDate })

describe('pickTrip', () => {
  const trips = [t('past', '2026-10-01', '2026-10-04'), t('later', '2026-12-20', '2026-12-24'), t('soon', '2026-12-01', '2026-12-04')]
  it('opens the trip being travelled first', () => {
    expect(pickTrip([...trips, t('now', '2026-11-22', '2026-11-26')], '2026-11-24')?.id).toBe('now')
  })
  it('else the next one coming', () => {
    expect(pickTrip(trips, '2026-11-24')?.id).toBe('soon')
  })
  it('else the one that ended last, and nothing for no trips', () => {
    expect(pickTrip([t('a', '2026-01-01', '2026-01-03'), t('b', '2026-05-01', '2026-05-03')], '2026-11-24')?.id).toBe('b')
    expect(pickTrip([], '2026-11-24')).toBeNull()
  })
})
