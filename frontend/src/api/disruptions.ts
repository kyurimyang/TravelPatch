import { LLM_TIMEOUT_MS, postJson } from './http'
import type { InterpretRequest, InterpretResponse } from './types'

export function interpretDisruption(req: InterpretRequest): Promise<InterpretResponse> {
  return postJson<InterpretResponse>('/disruptions/interpret', req, { timeoutMs: LLM_TIMEOUT_MS })
}
