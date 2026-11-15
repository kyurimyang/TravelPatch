// TEMPORARY mock for the Confirm screen (decision: build the screen first, wire the API in stage 6).
// These types are hand-written on purpose and must be replaced by types generated from the backend
// OpenAPI once a parse endpoint exists. Backend `DraftItinerary` (app/schemas/itinerary.py) carries
// times/issues; place matching ("found" / "ambiguous") is what the Places step will add.

import type { Tier } from '../lib/tier'

export type PlaceIcon = 'shrine' | 'market' | 'sight' | 'nightview' | 'food' | 'shopping'

export type PlaceCandidate = { id: string; name: string; sub: string }

export type DraftItemView = {
  id: string
  /** "HH:MM" display string (the backend sends minutes since midnight). */
  time: string
  /** What the user actually typed, shown so they can see how it was read. */
  rawText: string
  name: string
  categoryLabel: string
  address: string
  icon: PlaceIcon
  /** found = one confident match; ambiguous = user must pick from `candidates`. */
  match: 'found' | 'ambiguous'
  candidates?: PlaceCandidate[]
  /** Default tier the LLM would suggest (source = llm_default); the user can change it on the Grade screen. */
  recommendedTier: Tier
}

export type DraftDayView = { label: string; dateLabel: string; items: DraftItemView[] }

export const MOCK_TRIP_TITLE = '도쿄 1박 2일'

export const MOCK_DAYS: DraftDayView[] = [
  {
    label: 'DAY 1',
    dateLabel: '10월 8일 목요일',
    items: [
      { id: 'd1-1', time: '09:00', rawText: '9시 아사쿠사', name: '센소지', categoryLabel: '관광', address: '도쿄 다이토구', icon: 'shrine', match: 'found', recommendedTier: 'must' },
      { id: 'd1-2', time: '12:00', rawText: '점심 츠키지', name: '츠키지 장외시장', categoryLabel: '식사', address: '도쿄 주오구', icon: 'market', match: 'found', recommendedTier: 'nice' },
      { id: 'd1-3', time: '14:30', rawText: '시부야 스카이', name: '시부야 스카이', categoryLabel: '관광', address: '도쿄 시부야구', icon: 'nightview', match: 'found', recommendedTier: 'must' },
      {
        id: 'd1-4',
        time: '18:00',
        rawText: '시부야 저녁',
        name: '어느 곳인가요?',
        categoryLabel: '식사',
        address: '',
        icon: 'food',
        match: 'ambiguous',
        candidates: [
          { id: 'c1', name: '시부야 요코초', sub: '식당가 · 도쿄 시부야구' },
          { id: 'c2', name: '노게 요코초 골목', sub: '골목 식당가 · 도쿄 시부야구' },
        ],
        recommendedTier: 'optional',
      },
    ],
  },
  {
    label: 'DAY 2',
    dateLabel: '10월 9일 금요일',
    items: [
      { id: 'd2-1', time: '10:00', rawText: '10시 하라주쿠', name: '다케시타 거리', categoryLabel: '쇼핑', address: '도쿄 시부야구', icon: 'shopping', match: 'found', recommendedTier: 'nice' },
      { id: 'd2-2', time: '13:00', rawText: '점심', name: '오모테산도 카페', categoryLabel: '식사', address: '도쿄 시부야구', icon: 'food', match: 'found', recommendedTier: 'optional' },
      { id: 'd2-3', time: '15:00', rawText: '메이지 신궁', name: '메이지 신궁', categoryLabel: '관광', address: '도쿄 시부야구', icon: 'sight', match: 'found', recommendedTier: 'nice' },
    ],
  },
]
