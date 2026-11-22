// Paste structuring (2026-11-23): the draft says where each item is; the trip keeps it without
// searching what is already known and never searches by the title.
import { describe, expect, it } from 'vitest'
import type { DraftItinerary } from '../api/types'
import { DEFAULT_END_DEADLINE } from '../store/trip'
import { tripFromDraft } from './tripFromDraft'

type DraftItem = DraftItinerary['days'][number]['items'][number]
type DraftDay = DraftItinerary['days'][number]

const item = (title: string, fields: Partial<DraftItem> = {}): DraftItem => ({
  title,
  category: 'sightseeing',
  role: 'activity',
  start: 600,
  end: 660,
  duration_estimated: false,
  place_source: 'none',
  ...fields,
})

const day = (items: DraftItem[], fields: Partial<DraftDay> = {}): DraftDay => ({
  day_label: null,
  items,
  legs: [],
  issues: [],
  ...fields,
})

const meta = {
  city: '도쿄',
  startDate: '2027-01-24',
  endDate: '2027-01-27',
  hotel: { title: '워싱턴 호텔', placeId: 'hotel-1' },
  travelMode: 'transit' as const,
  arrival: null,
  departure: null,
}

const flight = { airport_query: '나리타 국제공항', time: 600, buffer_minutes: 60, time_written: true, absorbed: [] }

describe('tripFromDraft places', () => {
  it('searches a written name together with its address', () => {
    const trip = tripFromDraft(
      { days: [day([item('Fumotoya', { place_source: 'written', place_query: 'Fumotoya', address: '2-2-1 Nishi-Shinjuku' })])] },
      meta,
    )
    expect(trip.days[0].items[0].placeQuery).toBe('Fumotoya 2-2-1 Nishi-Shinjuku')
  })

  it('puts hotel items at the registered hotel at once', () => {
    const trip = tripFromDraft({ days: [day([item('체크인', { place_source: 'hotel', role: 'lodging' })])] }, meta)
    expect(trip.days[0].items[0].placeId).toBe('hotel-1')
  })

  it('points an item inside an earlier one at that item, without a search', () => {
    const trip = tripFromDraft(
      {
        days: [
          day([
            item('Tokyo Disneyland', { place_source: 'written', place_query: 'Tokyo Disneyland' }),
            item('Queen of Hearts', { place_source: 'venue', place_of: 0 }),
            item('간식', { place_source: 'previous', place_of: 0 }),
          ]),
        ],
      },
      meta,
    )
    const [, lunch, snack] = trip.days[0].items
    expect(lunch.placeFrom).toEqual({ id: 'd0-0', why: 'venue' })
    expect(snack.placeFrom).toEqual({ id: 'd0-0', why: 'previous' })
    expect(lunch.placeQuery).toBeNull()
  })

  it('searches the larger place when no item stands for it', () => {
    const trip = tripFromDraft(
      { days: [day([item('어트랙션', { place_source: 'venue', place_query: '도쿄 디즈니랜드' })])] },
      meta,
    )
    expect(trip.days[0].items[0].placeQuery).toBe('도쿄 디즈니랜드')
    expect(trip.days[0].items[0].placeFrom).toBeNull()
  })

  it('leaves an item with no written place for the user (no title search)', () => {
    const it0 = tripFromDraft({ days: [day([item('점심 - 스시', { place_source: 'none' })])] }, meta).days[0].items[0]
    expect([it0.placeId, it0.placeQuery, it0.placeFrom]).toEqual([null, null, null])
  })
})

describe('tripFromDraft day bounds', () => {
  it('takes the end time the text writes when every day agrees', () => {
    const trip = tripFromDraft({ days: [day([item('a')], { end_time: 1320 }), day([item('b')], { end_time: 1320 })] }, meta)
    expect(trip.endDeadline).toBe(1320)
  })

  it('keeps the default when the days disagree', () => {
    const trip = tripFromDraft({ days: [day([item('a')], { end_time: 1320 }), day([item('b')], { end_time: 1260 })] }, meta)
    expect(trip.endDeadline).toBe(DEFAULT_END_DEADLINE)
  })

  it('keeps the flights of the first and last day for Confirm to find their airport', () => {
    const departure = { ...flight, time: 760, buffer_minutes: 130, time_written: false }
    const trip = tripFromDraft(
      { days: [day([item('a')], { arrival: flight }), day([item('b')]), day([item('c')], { departure })] },
      meta,
    )
    expect(trip.textFlights).toEqual({ arrival: flight, departure })
  })

  it('does not replace flights the user entered at registration', () => {
    const entered = { time: 540, airport: { title: '하네다', placeId: 'hnd' }, bufferMinutes: null }
    const trip = tripFromDraft({ days: [day([item('a')], { arrival: flight })] }, { ...meta, arrival: entered })
    expect(trip.textFlights?.arrival ?? null).toBeNull()
    expect(trip.arrival).toBe(entered)
  })
})
