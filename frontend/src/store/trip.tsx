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

export type Trip = {
  city: string
  startDate: string
  endDate: string
  hotel: { title: string; placeId: string } | null
  /** How the traveler moves between places; travel times are estimated with it. */
  travelMode: TravelMode
  /** Latest return to the hotel, minutes since midnight. Default 22:00, changeable on Confirm. */
  endDeadline: number
  days: TripDay[]
  /** Stitched patches, oldest first: each is the change list against its day (invariant 6). */
  patches: SavedPatch[]
}

export const DEFAULT_END_DEADLINE = 22 * 60

type TripStore = {
  trip: Trip | null
  setTrip: (trip: Trip | null) => void
  /** Change one item, leaving everything else as it is. */
  updateItem: (itemId: string, patch: Partial<Omit<TripItem, 'id'>>) => void
  /** Stitch a patch onto its day (idempotent by patch id). */
  stitch: (patch: SavedPatch) => void
  /** Take the latest patch of a day back off. */
  unstitch: (patchId: string) => void
}

const STORAGE_KEY = 'trippatch.trip.v1'
const TripContext = createContext<TripStore | null>(null)

// Storage can be missing or throw (private window, blocked site data): the app then keeps the trip
// in memory only and still works for this visit.
function load(): Trip | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    // Trips saved before travel modes or patches existed get the old behaviour.
    return raw ? ({ travelMode: 'transit', patches: [], ...JSON.parse(raw) } as Trip) : null
  } catch {
    return null
  }
}

function save(trip: Trip | null): void {
  try {
    if (trip) localStorage.setItem(STORAGE_KEY, JSON.stringify(trip))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore: see load()
  }
}

export function TripProvider({ children }: { children: ReactNode }) {
  const [trip, setTrip] = useState<Trip | null>(load)

  useEffect(() => save(trip), [trip])

  const updateItem: TripStore['updateItem'] = (itemId, patch) =>
    setTrip((t) =>
      t && {
        ...t,
        days: t.days.map((d) => ({
          ...d,
          items: d.items.map((it) => (it.id === itemId ? { ...it, ...patch } : it)),
        })),
      },
    )

  const stitch: TripStore['stitch'] = (patch) => setTrip((t) => t && applyPatch(t, patch))
  const unstitch: TripStore['unstitch'] = (id) => setTrip((t) => t && undoPatch(t, id))

  return (
    <TripContext.Provider value={{ trip, setTrip, updateItem, stitch, unstitch }}>{children}</TripContext.Provider>
  )
}

export function useTrip(): TripStore {
  const store = useContext(TripContext)
  if (!store) throw new Error('useTrip must be used inside <TripProvider>')
  return store
}
