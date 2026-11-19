// The trips being registered and travelled. Signed out, they stay on this device (guest). Signed
// in, they are the account's: a copy on this device (lib/accountTrips) saved to Supabase a moment
// after each change, refused when another device saved first (decisions 2026-11-18/19).
//
// What is kept follows the Google terms decision: the user's own titles and Google place_ids only.
// No coordinates, no Google names or opening hours: the server fetches those per request.
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import type { components } from '../api/schema'
import type { TravelMode } from '../api/types'
import {
  emptyCache,
  keepMine,
  markDeleted,
  markSaved,
  mergeServer,
  putTrip,
  removeTrip,
  takeServer,
  unsaved,
  type AccountCache,
} from '../lib/accountTrips'
import { applyPatch, undoPatch, type SavedPatch } from '../lib/patches'
import { supabase } from '../lib/supabase'
import type { Tier } from '../lib/tier'
import { failureOf, loadTrips, saveTrip, type RpcClient } from '../lib/tripSync'
import { useAuth } from './auth'

type Schemas = components['schemas']
export type Category = Schemas['DraftItem']['category']
export type DraftIssue = Schemas['DraftIssue']

export type TripItem = {
  /** Local id, stable while the trip lives ("d0-3" = day 0, item 3). */
  id: string
  /** The words the user pasted. Shown everywhere instead of Google's name. */
  title: string
  category: Category
  /** Minutes since midnight. null = not known yet (an issue the user fixes on Confirm). */
  start: number | null
  end: number | null
  /** End was filled from the category default length, not written by the user. */
  durationEstimated: boolean
  reservationTime: number | null
  note: string | null
  /** Place name from the line ("오모테산도 산책" -> "오모테산도"), searched instead of the title.
   *  Missing on trips saved before 2026-11-18. */
  placeQuery?: string | null
  /** Google place_id the user picked. null = not picked yet. */
  placeId: string | null
  tier: Tier
  /** Taken out by a stitched patch (kept in the list, shown struck through, not recovered). */
  dropped?: boolean
  /** Its time or place was changed by a stitched patch. */
  patched?: boolean
  /** Replaced by a nearby place in a patch. The place itself is not stored (Google terms). */
  substituted?: boolean
}

export type TripDay = {
  /** ISO date "2026-10-08". */
  date: string
  /** The heading the pasted text used ("1일차"), if any. */
  label: string | null
  items: TripItem[]
  issues: DraftIssue[]
}

/** A flight that bounds a day, as the user entered it (never looked up). */
export type TripFlight = {
  /** Local minutes: landing for the arrival, take-off for the departure. */
  time: number
  /** The user's words + Google place_id, like the hotel (no Google name stored). */
  airport: { title: string; placeId: string }
  /** null = the server default (60 after landing, 180 before take-off). */
  bufferMinutes: number | null
}

export type Trip = {
  /** Local id, made when the trip is registered. */
  id: string
  city: string
  startDate: string
  endDate: string
  hotel: { title: string; placeId: string } | null
  /** How the traveler moves between places; travel times are estimated with it. */
  travelMode: TravelMode
  /** Latest return to the hotel, minutes since midnight. Default 22:00, changeable on Confirm. */
  endDeadline: number
  /** Lands on the first day: that day starts at the airport. */
  arrival: TripFlight | null
  /** Takes off on the last day: that day ends at the airport. */
  departure: TripFlight | null
  days: TripDay[]
  /** Stitched patches, oldest first: each is the change list against its day (invariant 6). */
  patches: SavedPatch[]
}

export const DEFAULT_END_DEADLINE = 22 * 60

/** Where the trips on screen are kept, and how saving to the account is going. */
export type SyncState =
  | { kind: 'guest' } // signed out: trips on this device only
  | { kind: 'loading' } // signed in, the account is being read
  | { kind: 'saved' } // everything here is in the account
  | { kind: 'saving' }
  | { kind: 'offline' } // waiting for the network; nothing is lost
  | { kind: 'signed-out' } // the session ended: sign in again to save
  | { kind: 'error' } // refused for another reason; retried after the next change

/** Another device changed (or deleted) a trip that has unsaved changes here. */
export type Conflict = { tripId: string; reason: 'stale' | 'gone' }

type TripStore = {
  /** The trip being looked at (Main, Recover, ...). */
  trip: Trip | null
  /** Every trip of the guest on this device, or of the signed-in account, in the order made. */
  trips: Trip[]
  /** Replace the current trip; a trip with a new id is added and becomes current. null removes it. */
  setTrip: (trip: Trip | null) => void
  selectTrip: (id: string) => void
  deleteTrip: (id: string) => void
  /** Change one item of the current trip, leaving everything else as it is. */
  updateItem: (itemId: string, patch: Partial<Omit<TripItem, 'id'>>) => void
  /** Stitch a patch onto its day of the current trip (idempotent by patch id). */
  stitch: (patch: SavedPatch) => void
  /** Take the latest patch of a day back off. */
  unstitch: (patchId: string) => void
  sync: SyncState
  conflict: Conflict | null
  /** "theirs": take the other device's copy. "mine": save this device's copy over it. */
  resolveConflict: (choice: 'theirs' | 'mine') => Promise<void>
  /** Guest trips on this device to offer moving into the account after sign-in (0 = do not ask). */
  guestToMove: number
  /** true: move them into the account (they are saved like new trips). false: leave them on this
   *  device as guest trips, and do not ask again until the next sign-in. */
  moveGuestTrips: (move: boolean) => void
}

type Saved = { trips: Trip[]; currentId: string | null }

const STORAGE_KEY = 'trippatch.trips.v2'
const OLD_KEY = 'trippatch.trip.v1' // one trip, before the trip list existed
const ACCOUNT_KEY = 'trippatch.account.v1' // the signed-in account's copy (lib/accountTrips)
const SAVE_DELAY_MS = 1500 // wait for a pause in typing before saving
const TripContext = createContext<TripStore | null>(null)

// Fields added after a trip may have been saved get their old behaviour.
const upgrade = (t: Partial<Trip>): Trip =>
  ({ travelMode: 'transit', patches: [], arrival: null, departure: null, id: crypto.randomUUID(), ...t }) as Trip

// Storage can be missing or throw (private window, blocked site data): the app then keeps trips
// in memory only and still works for this visit.
function load(): Saved {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const saved = JSON.parse(raw) as Saved
      return { trips: saved.trips.map(upgrade), currentId: saved.currentId }
    }
    const old = localStorage.getItem(OLD_KEY)
    if (old) {
      const trip = upgrade(JSON.parse(old))
      return { trips: [trip], currentId: trip.id }
    }
  } catch {
    // fall through
  }
  return { trips: [], currentId: null }
}

function save(saved: Saved): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved))
    localStorage.removeItem(OLD_KEY)
  } catch {
    // ignore: see load()
  }
}

function loadAccount(): AccountCache | null {
  try {
    const raw = localStorage.getItem(ACCOUNT_KEY)
    return raw ? (JSON.parse(raw) as AccountCache) : null
  } catch {
    return null
  }
}

function saveAccount(cache: AccountCache | null): void {
  try {
    if (cache) localStorage.setItem(ACCOUNT_KEY, JSON.stringify(cache))
    else localStorage.removeItem(ACCOUNT_KEY)
  } catch {
    // ignore: see load()
  }
}

// supabase-js's rpc, narrowed to what lib/tripSync needs.
const rpcClient: RpcClient | null = supabase
  ? { rpc: (fn, args) => supabase!.rpc(fn, args) }
  : null

export function TripProvider({ children }: { children: ReactNode }) {
  const { ready, user } = useAuth()
  const [guest, setGuest] = useState<Saved>(load)
  const [account, setAccount] = useState<AccountCache | null>(loadAccount)
  const [sync, setSync] = useState<SyncState>({ kind: 'guest' })
  const [conflict, setConflict] = useState<Conflict | null>(null)
  const [online, setOnline] = useState(0) // bumped when the network comes back
  const [loadedFor, setLoadedFor] = useState<string | null>(null) // account read from the server
  const [moveAnswered, setMoveAnswered] = useState(false)
  const flushing = useRef(false)
  // Trips refused for a reason a retry will not fix, with the edit count that was refused.
  const refused = useRef(new Map<string, number>())

  const owner = ready && user && rpcClient ? user.id : null
  const signedIn = owner !== null && account?.owner === owner

  useEffect(() => save(guest), [guest])
  useEffect(() => saveAccount(account), [account])

  // Sign-in: read the account and merge it with what this device has not saved yet.
  // Sign-out: forget the account's copy on this device (decision 2026-11-19, shared computers).
  useEffect(() => {
    if (!ready) return
    setLoadedFor(null)
    setMoveAnswered(false)
    if (!owner) {
      setAccount(null)
      setConflict(null)
      setSync({ kind: 'guest' })
      return
    }
    let cancelled = false
    setAccount((prev) => (prev?.owner === owner ? prev : emptyCache(owner)))
    setSync({ kind: 'loading' })
    loadTrips(rpcClient!).then((result) => {
      if (cancelled) return
      if (result.ok) {
        setAccount((prev) => mergeServer(owner, result.trips, prev))
        setLoadedFor(owner)
        setSync({ kind: 'saved' })
      } else {
        setSync({ kind: result.reason === 'offline' ? 'offline' : result.reason === 'signed-out' ? 'signed-out' : 'error' })
      }
    })
    return () => {
      cancelled = true
    }
  }, [ready, owner])

  useEffect(() => {
    const back = () => setOnline((n) => n + 1)
    window.addEventListener('online', back)
    return () => window.removeEventListener('online', back)
  }, [])

  /** Send what the server does not have: deletes first, then unsaved trips, one at a time. */
  const flush = useCallback(async () => {
    if (!owner || flushing.current || !supabase) return
    flushing.current = true
    try {
      const cache = account
      if (!cache || cache.owner !== owner) return
      setSync({ kind: 'saving' })
      let held = false // something was left for the user (refused): not "saved"

      for (const { id } of cache.deletes) {
        const { error } = await supabase.from('trips').delete().eq('id', id)
        if (error) {
          setSync({ kind: failureOf(error) === 'offline' ? 'offline' : 'error' })
          return
        }
        setAccount((prev) => (prev ? markDeleted(prev, id) : prev))
      }

      for (const entry of unsaved(cache)) {
        const id = entry.trip.id
        if (conflict?.tripId === id) continue
        if (refused.current.get(id) === entry.edits) {
          held = true
          continue
        }
        const result = await saveTrip(rpcClient!, entry.trip, entry.revision)
        if (result.ok) {
          setAccount((prev) => (prev ? markSaved(prev, id, result.revision, entry.edits) : prev))
          continue
        }
        switch (result.reason) {
          case 'stale':
          case 'gone':
            setConflict({ tripId: id, reason: result.reason })
            continue
          case 'offline':
            setSync({ kind: 'offline' })
            return
          case 'signed-out':
            setSync({ kind: 'signed-out' })
            return
          case 'forbidden':
          case 'too-large':
          case 'unknown':
            refused.current.set(id, entry.edits)
            setSync({ kind: 'error' })
            return
        }
      }
      setSync({ kind: held ? 'error' : 'saved' })
    } finally {
      flushing.current = false
    }
  }, [owner, account, conflict])

  // Save a moment after the last change, and again when the network comes back.
  useEffect(() => {
    if (!signedIn || !account) return
    const pending =
      account.deletes.length > 0 ||
      unsaved(account).some((e) => e.trip.id !== conflict?.tripId && refused.current.get(e.trip.id) !== e.edits)
    if (!pending) return
    const timer = setTimeout(flush, SAVE_DELAY_MS)
    return () => clearTimeout(timer)
  }, [signedIn, account, conflict, online, flush])

  const resolveConflict: TripStore['resolveConflict'] = async (choice) => {
    if (!conflict || !owner) return
    const result = await loadTrips(rpcClient!)
    if (!result.ok) {
      setSync({ kind: result.reason === 'offline' ? 'offline' : 'error' })
      return
    }
    const server = result.trips.find((s) => s.trip.id === conflict.tripId) ?? null
    setAccount((prev) => {
      if (!prev) return prev
      return choice === 'theirs'
        ? takeServer(prev, conflict.tripId, server)
        : keepMine(prev, conflict.tripId, server?.revision ?? null)
    })
    setConflict(null)
  }

  // Asked only once the account has been read, so the question is not mixed with a failed load.
  const guestToMove = signedIn && loadedFor === owner && !moveAnswered ? guest.trips.length : 0

  const moveGuestTrips: TripStore['moveGuestTrips'] = (move) => {
    setMoveAnswered(true)
    if (!move || !signedIn) return
    const moving = guest.trips
    setAccount((c) =>
      c ? moving.reduce((acc, t) => (acc.entries.some((e) => e.trip.id === t.id) ? acc : putTrip(acc, t)), c) : c,
    )
    setGuest({ trips: [], currentId: null })
  }

  // --- what the screens see and do: the account when signed in, else this device's guest trips ---

  const trips = signedIn ? account!.entries.map((e) => e.trip) : guest.trips
  const currentId = signedIn ? account!.currentId : guest.currentId
  const trip = trips.find((t) => t.id === currentId) ?? null

  const setTrip: TripStore['setTrip'] = (next) => {
    if (signedIn) {
      setAccount((c) => {
        if (!c) return c
        if (next === null) return c.currentId ? removeTrip(c, c.currentId) : c
        return { ...putTrip(c, next), currentId: next.id }
      })
      return
    }
    setGuest((s) => {
      if (next === null) {
        return { trips: s.trips.filter((t) => t.id !== s.currentId), currentId: null }
      }
      const exists = s.trips.some((t) => t.id === next.id)
      return {
        trips: exists ? s.trips.map((t) => (t.id === next.id ? next : t)) : [...s.trips, next],
        currentId: next.id,
      }
    })
  }

  const selectTrip: TripStore['selectTrip'] = (id) =>
    signedIn
      ? setAccount((c) => (c ? { ...c, currentId: id } : c))
      : setGuest((s) => ({ ...s, currentId: id }))

  const deleteTrip: TripStore['deleteTrip'] = (id) =>
    signedIn
      ? setAccount((c) => (c ? removeTrip(c, id) : c))
      : setGuest((s) => ({
          trips: s.trips.filter((t) => t.id !== id),
          currentId: s.currentId === id ? null : s.currentId,
        }))

  /** Apply f to the current trip. */
  const editCurrent = (f: (t: Trip) => Trip) => {
    if (signedIn) {
      setAccount((c) => {
        const current = c?.entries.find((e) => e.trip.id === c.currentId)?.trip
        return c && current ? putTrip(c, f(current)) : c
      })
      return
    }
    setGuest((s) => ({ ...s, trips: s.trips.map((t) => (t.id === s.currentId ? f(t) : t)) }))
  }

  const updateItem: TripStore['updateItem'] = (itemId, patch) =>
    editCurrent((t) => ({
      ...t,
      days: t.days.map((d) => ({
        ...d,
        items: d.items.map((it) => (it.id === itemId ? { ...it, ...patch } : it)),
      })),
    }))

  const stitch: TripStore['stitch'] = (patch) => editCurrent((t) => applyPatch(t, patch))
  const unstitch: TripStore['unstitch'] = (id) => editCurrent((t) => undoPatch(t, id))

  return (
    <TripContext.Provider
      value={{
        trip,
        trips,
        setTrip,
        selectTrip,
        deleteTrip,
        updateItem,
        stitch,
        unstitch,
        sync: signedIn ? sync : { kind: 'guest' },
        conflict,
        resolveConflict,
        guestToMove,
        moveGuestTrips,
      }}
    >
      {children}
    </TripContext.Provider>
  )
}

export function useTrip(): TripStore {
  const store = useContext(TripContext)
  if (!store) throw new Error('useTrip must be used inside <TripProvider>')
  return store
}
