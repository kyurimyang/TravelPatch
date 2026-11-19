// The trip being registered and travelled, kept in the browser (decision 2026-11-17: no login yet,
// so no DB). One trip at a time for now; the trip list comes later.
//
// What is kept follows the Google terms decision: the user's own titles and Google place_ids only.
// No coordinates, no Google names or opening hours: the server fetches those per request.
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { components } from '../api/schema'
import type { TravelMode } from '../api/types'
import { applyPatch, undoPatch, type SavedPatch } from '../lib/patches'
import type { Tier } from '../lib/tier'

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

type TripStore = {
  /** The trip being looked at (Main, Recover, ...). */
  trip: Trip | null
  /** Every trip kept on this device, in the order they were made. */
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
}

type Saved = { trips: Trip[]; currentId: string | null }

const STORAGE_KEY = 'trippatch.trips.v2'
const OLD_KEY = 'trippatch.trip.v1' // one trip, before the trip list existed
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

export function TripProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<Saved>(load)

  useEffect(() => save(saved), [saved])

  const trip = saved.trips.find((t) => t.id === saved.currentId) ?? null

  /** Apply f to the current trip. */
  const editCurrent = (f: (t: Trip) => Trip) =>
    setSaved((s) => ({ ...s, trips: s.trips.map((t) => (t.id === s.currentId ? f(t) : t)) }))

  const setTrip: TripStore['setTrip'] = (next) =>
    setSaved((s) => {
      if (next === null) {
        return { trips: s.trips.filter((t) => t.id !== s.currentId), currentId: null }
      }
      const exists = s.trips.some((t) => t.id === next.id)
      return {
        trips: exists ? s.trips.map((t) => (t.id === next.id ? next : t)) : [...s.trips, next],
        currentId: next.id,
      }
    })

  const selectTrip: TripStore['selectTrip'] = (id) => setSaved((s) => ({ ...s, currentId: id }))

  const deleteTrip: TripStore['deleteTrip'] = (id) =>
    setSaved((s) => ({
      trips: s.trips.filter((t) => t.id !== id),
      currentId: s.currentId === id ? null : s.currentId,
    }))

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
      value={{ trip, trips: saved.trips, setTrip, selectTrip, deleteTrip, updateItem, stitch, unstitch }}
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
