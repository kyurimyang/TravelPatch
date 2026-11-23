import { describe, expect, it } from 'vitest'
import { closable, minutesLabel, quickResponse } from './quick'
import { samplePlan } from './recovery'

const titleOf = (id: string) => ({ meiji: '메이지 신궁' })[id] ?? id

describe('quickResponse', () => {
  it('turns "30분 지연" into a delay without the LLM', () => {
    const r = quickResponse('delay', 30, 600, 'hotel', titleOf)
    expect(r.event).toEqual({ type: 'DELAY', occurred_at: 600, start_time: 630, location_id: 'hotel' })
    expect(r.chips).toEqual(['10:30부터 움직일 수 있어요'])
  })
  it('rain from now, a closure of a chosen place, and tiredness', () => {
    expect(quickResponse('rain', 0, 720, 'meiji', titleOf).event).toMatchObject({ type: 'WEATHER', start_time: 720, end_time: null })
    expect(quickResponse('closed', 'meiji', 540, 'hotel', titleOf)).toMatchObject({
      event: { type: 'CLOSURE', activity_id: 'meiji' },
      chips: ['메이지 신궁 · 문을 닫았어요'],
    })
    expect(quickResponse('tired', null, 540, 'hotel', titleOf).event).toMatchObject({ type: 'FATIGUE', walking_ratio: 0.5 })
  })
  it('never runs past midnight', () => {
    expect(quickResponse('late', 180, 23 * 60, 'hotel', titleOf).event).toMatchObject({ start_time: 24 * 60 })
  })
})

describe('helpers', () => {
  it('offers only places not over yet', () => {
    const left = closable(samplePlan(), 12 * 60)
    expect(left.every((a) => a.planned_end > 12 * 60)).toBe(true)
  })
  it('labels minutes', () => {
    expect([0, 15, 60, 90, 120].map(minutesLabel)).toEqual(['지금', '15분', '1시간', '1시간 30분', '2시간'])
  })
})
