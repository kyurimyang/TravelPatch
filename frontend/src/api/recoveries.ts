import { postJson } from './http'
import type { RecoveryInput, RecoveryResponse } from './types'

export { ApiError } from './http'

export function createRecovery(input: RecoveryInput): Promise<RecoveryResponse> {
  return postJson<RecoveryResponse>('/recoveries', input)
}
