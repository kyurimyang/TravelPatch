import { describe, expect, it } from 'vitest'
import type { Trip } from '../store/trip'
import { failureOf, loadTrips, saveTrip, type RpcClient, type RpcError } from './tripSync'

const trip = {
  id: '6f1c0a52-0000-4000-8000-000000000001',
  city: '도쿄',
  startDate: '2026-10-08',
  endDate: '2026-10-08',
  hotel: null,
  travelMode: 'transit',
  endDeadline: 1320,
  arrival: null,
  departure: null,
  days: [],
  patches: [],
} satisfies Trip

/** A fake client that answers every call the same way and remembers what it was asked. */
function fake(answer: { data?: unknown; error?: RpcError } | 'throw') {
  const calls: { fn: string; args?: Record<string, unknown> }[] = []
  const client: RpcClient = {
    rpc: async (fn, args) => {
      calls.push({ fn, args })
      if (answer === 'throw') throw new TypeError('Failed to fetch')
      return { data: answer.data ?? null, error: answer.error ?? null }
    },
  }
  return { client, calls }
}

describe('failureOf', () => {
  it.each([
    ['PT409', 'stale'],
    ['23505', 'stale'],
    ['PT410', 'gone'],
    ['28000', 'signed-out'],
    ['PGRST301', 'signed-out'],
    ['42501', 'forbidden'],
    ['22023', 'too-large'],
    ['XX000', 'unknown'],
  ] as const)('%s -> %s', (code, reason) => {
    expect(failureOf({ code, message: 'x' })).toBe(reason)
  })

  it('treats a codeless fetch failure as offline', () => {
    expect(failureOf({ code: '', message: 'TypeError: Failed to fetch' })).toBe('offline')
  })

  it('does not guess offline for other codeless errors', () => {
    expect(failureOf({ message: 'something else' })).toBe('unknown')
  })
})

describe('saveTrip', () => {
  it('sends the trip and the revision this device saw, and returns the new one', async () => {
    const { client, calls } = fake({ data: 4 })
    expect(await saveTrip(client, trip, 3)).toEqual({ ok: true, revision: 4 })
    expect(calls).toEqual([{ fn: 'save_trip', args: { trip, base_revision: 3 } }])
  })

  it('reports a stale save', async () => {
    const { client } = fake({ error: { code: 'PT409', message: 'stale revision' } })
    expect(await saveTrip(client, trip, 3)).toEqual({ ok: false, reason: 'stale' })
  })

  it('reports offline when the request cannot be sent', async () => {
    const { client } = fake('throw')
    expect(await saveTrip(client, trip, null)).toEqual({ ok: false, reason: 'offline' })
  })
})

describe('loadTrips', () => {
  it('splits the revision off each trip', async () => {
    const { client } = fake({ data: [{ ...trip, revision: 7 }] })
    expect(await loadTrips(client)).toEqual({ ok: true, trips: [{ trip, revision: 7 }] })
  })

  it('returns no trips for an account without any', async () => {
    const { client } = fake({ data: [] })
    expect(await loadTrips(client)).toEqual({ ok: true, trips: [] })
  })

  it('reports a signed-out user', async () => {
    const { client } = fake({ error: { code: 'PGRST301', message: 'JWT expired' } })
    expect(await loadTrips(client)).toEqual({ ok: false, reason: 'signed-out' })
  })
})
