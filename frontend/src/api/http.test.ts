// A7 (review 2026-11-19): a request with no answer kept "읽는 중…" on screen forever.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { getJson, postJson, RequestTimeoutError } from './http'

/** A server that never answers; it only gives up when the request is aborted. */
function hangingFetch() {
  return vi.fn((_url: string, init?: RequestInit) =>
    new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(init.signal!.reason))
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('request timeout', () => {
  it('gives up on a POST that never answers', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', hangingFetch())
    const req = postJson('/recoveries', {}, { timeoutMs: 5_000 })
    const done = expect(req).rejects.toBeInstanceOf(RequestTimeoutError)
    await vi.advanceTimersByTimeAsync(5_000)
    await done
  })

  it('gives up on a GET too, after the default', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', hangingFetch())
    const req = getJson('/places/search', { q: 'x' })
    const done = expect(req).rejects.toBeInstanceOf(RequestTimeoutError)
    await vi.advanceTimersByTimeAsync(20_000)
    await done
  })

  it('does not fire once the answer is in', async () => {
    vi.useFakeTimers()
    const ok = vi.fn(async () => new Response(JSON.stringify({ a: 1 }), { status: 200 }))
    vi.stubGlobal('fetch', ok)
    await expect(postJson('/x', {})).resolves.toEqual({ a: 1 })
    expect(vi.getTimerCount()).toBe(0)
  })
})
