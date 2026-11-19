// The signed-in user's trips as this device holds them (C3, decision 2026-11-19): a copy of the
// account plus what has not reached the server yet. Pure functions; the store does the I/O.
//
// Guest trips live elsewhere (store/trip.tsx, trippatch.trips.v2). This copy is tied to one
// account (`owner`) and is removed on sign-out, so a shared computer keeps nobody's trips.
import type { Trip } from '../store/trip'
import type { SyncedTrip } from './tripSync'

export type AccountEntry = {
  trip: Trip
  /** The server revision this device last saw. null = never saved to the account. */
  revision: number | null
  /** Changes made on this device, and how many of them the server has. Different = unsaved.
   *  A count, not a flag: a change made while a save is on its way stays unsaved. */
  edits: number
  savedEdits: number
}

/** A trip deleted here that the server has not been told about yet. */
export type PendingDelete = { id: string }

export type AccountCache = {
  owner: string
  entries: AccountEntry[]
  deletes: PendingDelete[]
  currentId: string | null
}

export const emptyCache = (owner: string): AccountCache => ({ owner, entries: [], deletes: [], currentId: null })

export const isUnsaved = (e: AccountEntry): boolean => e.edits !== e.savedEdits

/** Entries with changes the server does not have, oldest trip first. */
export const unsaved = (cache: AccountCache): AccountEntry[] => cache.entries.filter(isUnsaved)

/**
 * The account as the server sent it, merged with what this device has not saved.
 * - on the server, nothing unsaved here      -> the server's copy
 * - on the server, unsaved changes here      -> kept; saving it finds out if the server moved on
 * - not on the server, never saved           -> kept (a new trip, about to be saved)
 * - not on the server, saved before, no changes -> deleted on another device: dropped here too
 * - not on the server, saved before, changes -> kept; saving it reports "gone" and the user decides
 * - deleted here, not yet on the server      -> not brought back
 * A cache of another account is ignored (another person used this device).
 */
export function mergeServer(owner: string, server: SyncedTrip[], prev: AccountCache | null): AccountCache {
  const local = prev?.owner === owner ? prev : emptyCache(owner)
  const deleting = new Set(local.deletes.map((d) => d.id))
  const byId = new Map(local.entries.map((e) => [e.trip.id, e]))
  const onServer = new Set(server.map((s) => s.trip.id))

  const fromServer: AccountEntry[] = server
    .filter((s) => !deleting.has(s.trip.id))
    .map((s) => {
      const mine = byId.get(s.trip.id)
      if (mine && isUnsaved(mine)) return mine
      return { trip: s.trip, revision: s.revision, edits: 0, savedEdits: 0 }
    })
  const onlyHere = local.entries.filter(
    (e) => !onServer.has(e.trip.id) && (e.revision === null || isUnsaved(e)),
  )
  const entries = [...fromServer, ...onlyHere]
  const currentId = entries.some((e) => e.trip.id === local.currentId) ? local.currentId : null
  return { owner, entries, deletes: local.deletes, currentId }
}

/** Replace a trip (or add a new one) as a change made on this device. */
export function putTrip(cache: AccountCache, trip: Trip): AccountCache {
  const exists = cache.entries.some((e) => e.trip.id === trip.id)
  const entries = exists
    ? cache.entries.map((e) => (e.trip.id === trip.id ? { ...e, trip, edits: e.edits + 1 } : e))
    : [...cache.entries, { trip, revision: null, edits: 1, savedEdits: 0 }]
  return { ...cache, entries }
}

/** Remove a trip here; the server is told later unless it never had it. */
export function removeTrip(cache: AccountCache, id: string): AccountCache {
  const entry = cache.entries.find((e) => e.trip.id === id)
  if (!entry) return cache
  return {
    ...cache,
    entries: cache.entries.filter((e) => e.trip.id !== id),
    deletes: entry.revision === null ? cache.deletes : [...cache.deletes, { id }],
    currentId: cache.currentId === id ? null : cache.currentId,
  }
}

/** A save of `sentEdits` changes reached the server as `revision`. Later changes stay unsaved. */
export function markSaved(cache: AccountCache, id: string, revision: number, sentEdits: number): AccountCache {
  return {
    ...cache,
    entries: cache.entries.map((e) =>
      e.trip.id === id ? { ...e, revision, savedEdits: Math.max(e.savedEdits, sentEdits) } : e,
    ),
  }
}

export function markDeleted(cache: AccountCache, id: string): AccountCache {
  return { ...cache, deletes: cache.deletes.filter((d) => d.id !== id) }
}

/** Conflict, "take theirs": the server's copy replaces this device's (null = it was deleted). */
export function takeServer(cache: AccountCache, id: string, server: SyncedTrip | null): AccountCache {
  if (!server) {
    return {
      ...cache,
      entries: cache.entries.filter((e) => e.trip.id !== id),
      currentId: cache.currentId === id ? null : cache.currentId,
    }
  }
  const entry: AccountEntry = { trip: server.trip, revision: server.revision, edits: 0, savedEdits: 0 }
  return { ...cache, entries: cache.entries.map((e) => (e.trip.id === id ? entry : e)) }
}

/** Conflict, "keep mine": save this device's copy on top of the server's latest revision
 *  (null = it was deleted there, so it is saved again as a new trip). */
export function keepMine(cache: AccountCache, id: string, serverRevision: number | null): AccountCache {
  return {
    ...cache,
    entries: cache.entries.map((e) => (e.trip.id === id ? { ...e, revision: serverRevision } : e)),
  }
}
