import { LLM_TIMEOUT_MS, postJson } from './http'
import type { BuildRequest, InterpretRequest, InterpretResponse } from './types'

export function interpretDisruption(req: InterpretRequest): Promise<InterpretResponse> {
  return postJson<InterpretResponse>('/disruptions/interpret', req, { timeoutMs: LLM_TIMEOUT_MS })
}

/** The same rules again on edited drafts (an answered question, a fixed or removed chip): no LLM. */
export function buildDisruption(req: BuildRequest): Promise<InterpretResponse> {
  return postJson<InterpretResponse>('/disruptions/build', req)
}
