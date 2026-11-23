import { postJson } from './http'
import type { AddPlaceRequest, AddPlaceResponse, BuiltPlan, PlanRequest } from './types'

export function buildPlan(req: PlanRequest): Promise<BuiltPlan> {
  return postJson<BuiltPlan>('/plans/build', req)
}

/** "꼭 가고 싶은 곳": a picked place -> the MUST_VISIT event + the day's travel table with it. */
export function addPlace(req: AddPlaceRequest): Promise<AddPlaceResponse> {
  return postJson<AddPlaceResponse>('/plans/add-place', req)
}
