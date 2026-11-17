import { getJson } from './http'
import type { PlaceSearchResponse } from './types'

export function searchPlaces(q: string, city?: string): Promise<PlaceSearchResponse> {
  return getJson<PlaceSearchResponse>('/places/search', { q, city })
}
