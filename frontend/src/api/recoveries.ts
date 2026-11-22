import { LLM_TIMEOUT_MS, postJson } from './http'
import type { LockRequest, RecoveryRequest, RecoveryResponse, RestoreRequest, RestoreResponse } from './types'

export { ApiError } from './http'

/** `visited`: ids already done today; the server takes them out before the engine. */
export function createRecovery(input: RecoveryRequest): Promise<RecoveryResponse> {
  return postJson<RecoveryResponse>('/recoveries', input, { timeoutMs: LLM_TIMEOUT_MS })
}

/** "What if I keep X?" The server recomputes the candidate from `input` (never trusts ours). */
export function restoreActivity(req: RestoreRequest): Promise<RestoreResponse> {
  return postJson<RestoreResponse>('/recoveries/restore', req)
}

/** Recompute with these activities held at their original slots. */
export function lockActivities(req: LockRequest): Promise<RecoveryResponse> {
  return postJson<RecoveryResponse>('/recoveries/lock', req)
}
