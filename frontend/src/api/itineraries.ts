import { postJson } from './http'
import type { ParseResponse } from './types'

export function parseItinerary(text: string): Promise<ParseResponse> {
  return postJson<ParseResponse>('/itineraries/parse', { text })
}
