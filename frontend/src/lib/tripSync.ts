// Saving and loading a signed-in user's trips (C3, decisions 2026-11-18/19). The database keeps
// them in normalized tables; save_trip / load_trips (migration 0003) speak the browser's Trip shape.
//
// Every save sends the revision this device last saw. If another device saved since, the save is
// refused (PT409) instead of silently overwriting it. Failures come back as values, not throws, so
// the caller handles each reason (the switch is checked by TypeScript).
import type { Trip } from '../store/trip'

/** A trip as saved in the account, with the revision this device last saw. */
export type SyncedTrip = { trip: Trip; revision: number }

export type SyncFailure =
  | 'stale' // another device saved first: load again, then decide
  | 'gone' // deleted on another device
  | 'signed-out' // no session, or it expired
  | 'forbidden' // not this user's trip
  | 'too-large' // far bigger than the app makes
  | 'offline' // no network: keep it on this device and send it later
  | 'unknown'

export type SaveResult = { ok: true; revision: number } | { ok: false; reason: SyncFailure }
export type LoadResult = { ok: true; trips: SyncedTrip[] } | { ok: false; reason: SyncFailure }

/** The part of the Supabase client used here, so tests can pass a fake. */
export type RpcClient = {
  rpc: (fn: string, args?: Record<string, unknown>) => PromiseLike<{ data: unknown; error: RpcError | null }>
}
export type RpcError = { code?: string; message?: string }

/** The SQLSTATE (or PostgREST code) of a failed call -> what the app does about it. */
export function failureOf(error: RpcError): SyncFailure {
  switch (error.code) {
    case 'PT409':
    case '23505': // the same new trip inserted from two devices at once
      return 'stale'
    case 'PT410':
      return 'gone'
    case '28000':
    case 'PGRST301': // JWT expired
    case 'PGRST302':
      return 'signed-out'
    case '42501':
      return 'forbidden'
    case '22023':
      return 'too-large'
  }
  // supabase-js reports a network failure as an error without a code ("Failed to fetch").
  if (!error.code && /fetch|network/i.test(error.message ?? '')) return 'offline'
  return 'unknown'
}

export async function saveTrip(client: RpcClient, trip: Trip, baseRevision: number | null): Promise<SaveResult> {
  try {
    const { data, error } = await client.rpc('save_trip', { trip, base_revision: baseRevision })
    if (error) return { ok: false, reason: failureOf(error) }
    return { ok: true, revision: data as number }
  } catch {
    return { ok: false, reason: 'offline' } // fetch itself threw
  }
}

export async function loadTrips(client: RpcClient): Promise<LoadResult> {
  try {
    const { data, error } = await client.rpc('load_trips')
    if (error) return { ok: false, reason: failureOf(error) }
    const rows = (data ?? []) as (Trip & { revision: number })[]
    return { ok: true, trips: rows.map(({ revision, ...trip }) => ({ trip, revision })) }
  } catch {
    return { ok: false, reason: 'offline' }
  }
}
