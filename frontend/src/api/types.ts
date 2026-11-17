// Friendly names for the generated API types (schema.d.ts, made by `npm run gen:api` from
// the backend OpenAPI). Do not redefine API shapes by hand here: change the backend and regenerate.
import type { components } from './schema'

type Schemas = components['schemas']

export type Op = Schemas['Op']
export type RecoveryInput = Schemas['RecoveryInput']
export type RecoveryResponse = Schemas['RecoveryResponse']
export type RecoveryResult = Schemas['RecoveryResult']
export type RecoveryChange = Schemas['RecoveryChange']
export type Blocker = Schemas['Blocker']
export type InterpretRequest = Schemas['InterpretRequest']
export type InterpretResponse = Schemas['InterpretResponse']
export type DisruptionEvent = NonNullable<InterpretResponse['event']>

// What the UI needs to name an activity; the engine's changes only carry the id.
export type ActivityInfo = Pick<Schemas['Activity'], 'id' | 'title' | 'category'>
export type ParseResponse = Schemas['ParseResponse']
export type DraftItinerary = Schemas['DraftItinerary']
export type PlaceOption = Schemas['PlaceOption']
export type PlaceSearchResponse = Schemas['PlaceSearchResponse']
