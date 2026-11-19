import { getJson } from './http'
import type { PlaceSearchResponse } from './types'

/** `near` = the hotel's place_id: hits near it come first and far ones are flagged. */
export function searchPlaces(q: string, city?: string, near?: string): Promise<PlaceSearchResponse> {
  return getJson<PlaceSearchResponse>('/places/search', { q, city, near })
}
