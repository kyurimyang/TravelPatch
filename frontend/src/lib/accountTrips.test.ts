import { describe, expect, it } from 'vitest'
import type { Trip } from '../store/trip'
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
} from './accountTrips'

const ME = 'user-me'

function trip(id: string, city = '도쿄'): Trip {
  return {
    id,
    city,
    startDate: '2026-10-08',
    endDate: '2026-10-08',
    hotel: null,
    travelMode: 'transit',
    endDeadline: 1320,
    arrival: null,
    departure: null,
    days: [],
    patches: [],
  }
}

/** A cache where trip `id` was saved at `revision` and then changed `pending` more times. */
function savedThenChanged(id: string, revision: number, pending: number, city = '도쿄'): AccountCache {
  return {
    ...emptyCache(ME),
    entries: [{ trip: trip(id, city), revision, edits: 1 + pending, savedEdits: 1 }],
  }
}

const ids = (c: AccountCache) => c.entries.map((e) => e.trip.id)

describe('mergeServer', () => {
  it('takes the server copy when nothing here is unsaved', () => {
    const prev = savedThenChanged('a', 1, 0)
    const merged = mergeServer(ME, [{ trip: trip('a', '오사카'), revision: 2 }], prev)
    expect(merged.entries).toEqual([{ trip: trip('a', '오사카'), revision: 2, edits: 0, savedEdits: 0 }])
  })

  it('keeps unsaved changes made here, with the revision they were based on', () => {
    const prev = savedThenChanged('a', 1, 2, '교토')
    const merged = mergeServer(ME, [{ trip: trip('a', '오사카'), revision: 2 }], prev)
    expect(merged.entries[0]).toMatchObject({ trip: { city: '교토' }, revision: 1 })
    expect(unsaved(merged)).toHaveLength(1)
  })

  it('keeps a new trip the server has not seen yet', () => {
    const prev = putTrip(emptyCache(ME), trip('new'))
    expect(ids(mergeServer(ME, [], prev))).toEqual(['new'])
  })

  it('drops a saved trip that is gone from the server and unchanged here', () => {
    expect(ids(mergeServer(ME, [], savedThenChanged('a', 1, 0)))).toEqual([])
  })

  it('keeps a saved trip gone from the server if it has unsaved changes here', () => {
    expect(ids(mergeServer(ME, [], savedThenChanged('a', 1, 1)))).toEqual(['a'])
  })

  it('does not bring back a trip deleted here before the server heard of it', () => {
    const prev = removeTrip(savedThenChanged('a', 1, 0), 'a')
    const merged = mergeServer(ME, [{ trip: trip('a'), revision: 1 }], prev)
    expect(ids(merged)).toEqual([])
    expect(merged.deletes).toEqual([{ id: 'a' }])
  })

  it("ignores another account's copy left on this device", () => {
    const someoneElse = { ...savedThenChanged('theirs', 1, 3), owner: 'user-other' }
    const merged = mergeServer(ME, [{ trip: trip('mine'), revision: 1 }], someoneElse)
    expect(merged.owner).toBe(ME)
    expect(ids(merged)).toEqual(['mine'])
  })

  it('forgets the current trip if it no longer exists', () => {
    const prev = { ...savedThenChanged('a', 1, 0), currentId: 'a' }
    expect(mergeServer(ME, [], prev).currentId).toBeNull()
  })
})

describe('changes and saves', () => {
  it('counts a change made while a save is on its way as still unsaved', () => {
    let cache = putTrip(emptyCache(ME), trip('a')) // edits 1
    const sent = cache.entries[0].edits // a save of edit 1 leaves
    cache = putTrip(cache, trip('a', '오사카')) // edit 2 while waiting
    cache = markSaved(cache, 'a', 1, sent) // the save of edit 1 returns

    expect(cache.entries[0].revision).toBe(1)
    expect(unsaved(cache)).toHaveLength(1)
  })

  it('is saved once the last change has been sent', () => {
    let cache = putTrip(emptyCache(ME), trip('a'))
    cache = markSaved(cache, 'a', 1, 1)
    expect(unsaved(cache)).toEqual([])
  })

  it('does not ask the server to delete a trip it never had', () => {
    const cache = removeTrip(putTrip(emptyCache(ME), trip('new')), 'new')
    expect(cache.deletes).toEqual([])
  })

  it('forgets a delete once the server has it', () => {
    const cache = markDeleted(removeTrip(savedThenChanged('a', 1, 0), 'a'), 'a')
    expect(cache.deletes).toEqual([])
  })
})

describe('resolving a conflict', () => {
  it("take theirs: the server's copy replaces the unsaved one", () => {
    const cache = takeServer(savedThenChanged('a', 1, 2, '교토'), 'a', { trip: trip('a', '오사카'), revision: 3 })
    expect(cache.entries).toEqual([{ trip: trip('a', '오사카'), revision: 3, edits: 0, savedEdits: 0 }])
  })

  it('take theirs when it was deleted there: removed here', () => {
    const cache = takeServer({ ...savedThenChanged('a', 1, 2), currentId: 'a' }, 'a', null)
    expect(ids(cache)).toEqual([])
    expect(cache.currentId).toBeNull()
  })

  it('keep mine: still unsaved, now based on the latest revision', () => {
    const cache = keepMine(savedThenChanged('a', 1, 2, '교토'), 'a', 3)
    expect(cache.entries[0]).toMatchObject({ trip: { city: '교토' }, revision: 3 })
    expect(unsaved(cache)).toHaveLength(1)
  })

  it('keep mine when it was deleted there: saved again as a new trip', () => {
    const cache = keepMine(savedThenChanged('a', 1, 2), 'a', null)
    expect(cache.entries[0].revision).toBeNull()
    expect(unsaved(cache)).toHaveLength(1)
  })
})
