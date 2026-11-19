import { LLM_TIMEOUT_MS, postJson } from './http'
import type { ParseResponse } from './types'

export function parseItinerary(text: string): Promise<ParseResponse> {
  return postJson<ParseResponse>('/itineraries/parse', { text }, { timeoutMs: LLM_TIMEOUT_MS })
}
