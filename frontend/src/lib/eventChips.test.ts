import { describe, expect, it } from 'vitest'
import type { DisruptionEvent, EventDraft, Question } from '../api/types'
import { answer, TYPE_CHOICES } from './eventChips'
import { defaultVisited, inputFor, samplePlan, visitLocked } from './recovery'

const q = (kind: Question['kind'], field: Question['field']): Question => ({ kind, field, text: '', options: [], candidates: [] })

describe('answer', () => {
  it('sends a picked time as HH:MM for the server rules to read', () => {
    const draft: EventDraft = { type: 'WEATHER' }
    expect(answer(draft, q('time', 'time_from'), 13 * 60 + 5)).toEqual({ type: 'WEATHER', time_from: '13:05' })
  })

  it('a picked place wins over the words that did not match', () => {
    const draft: EventDraft = { type: 'CLOSURE', activity_hint: '거기' }
    expect(answer(draft, q('place', 'activity_id'), 'cafe')).toEqual({ type: 'CLOSURE', activity_id: 'cafe', activity_hint: null })
  })

  it('a chosen type starts a fresh draft', () => {
    expect(answer({ type: 'UNKNOWN', delay_minutes: 5 }, q('type', 'type'), 'WAIT')).toEqual({ type: 'WAIT' })
  })

  it('minutes fill their own field', () => {
    expect(answer({ type: 'WAIT', activity_hint: '라멘' }, q('minutes', 'wait_minutes'), 40)).toMatchObject({ wait_minutes: 40 })
  })

  it('offers every event a sentence can describe, never MUST_VISIT (it needs the map)', () => {
    expect(TYPE_CHOICES.map((c) => c.type)).not.toContain('MUST_VISIT')
    expect(TYPE_CHOICES.every((c) => !/[A-Z_]/.test(c.label))).toBe(true)
  })
})

describe('several events', () => {
  const rain: DisruptionEvent = { type: 'WEATHER', occurred_at: 720, start_time: 720, end_time: null, location_id: 'omotesando' }
  const queue: DisruptionEvent = { type: 'WAIT', occurred_at: 720, activity_id: 'ramen', minutes: 40, location_id: 'omotesando' }

  it('the request carries the extra events and wishes', () => {
    const inp = inputFor(samplePlan(), rain, [], [queue], ['indoor'])
    expect(inp.event).toBe(rain)
    expect(inp.more_events).toEqual([queue])
    expect(inp.wishes).toEqual(['indoor'])
  })

  it('a single event sends empty lists, as before', () => {
    const inp = inputFor(samplePlan(), rain)
    expect([inp.more_events, inp.wishes]).toEqual([[], []])
  })

  it('a place any event is about cannot be ticked as visited', () => {
    expect([...visitLocked(rain, [queue])]).toEqual(['ramen'])
    expect(defaultVisited(samplePlan(), rain, [queue])).not.toContain('ramen')
  })
})
