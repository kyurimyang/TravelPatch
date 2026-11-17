import { postJson } from './http'
import type { BuiltPlan, PlanRequest } from './types'

export function buildPlan(req: PlanRequest): Promise<BuiltPlan> {
  return postJson<BuiltPlan>('/plans/build', req)
}
