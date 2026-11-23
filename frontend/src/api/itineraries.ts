import { postJson } from './http'
import type { ParseResponse } from './types'

// Longer than other LLM calls: the server reads each day of the paste (in parallel, and a day
// that stopped early once more), so a long trip can take a while; cut at 60 s, it never arrived.
export const PARSE_TIMEOUT_MS = 120_000

export function parseItinerary(text: string): Promise<ParseResponse> {
  return postJson<ParseResponse>('/itineraries/parse', { text }, { timeoutMs: PARSE_TIMEOUT_MS })
}
