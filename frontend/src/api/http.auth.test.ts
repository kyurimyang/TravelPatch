// Decision 2026-11-22: a signed-in user's calls carry the token; 429 / 401 get their own words.
import { afterEach, describe, expect, it, vi } from 'vitest'

const session = vi.hoisted(() => ({ token: null as string | null }))
vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: async () => ({
        data: { session: session.token ? { access_token: session.token } : null },
      }),
    },
  },
}))

import { accessMessage, ApiError, getJson, postJson } from './http'

function okFetch() {
  return vi.fn(async (_url: string, _init?: RequestInit) => new Response('{}', { status: 200 }))
}

afterEach(() => {
  vi.unstubAllGlobals()
  session.token = null
})

describe('auth header', () => {
  it('sends the token when signed in, next to the JSON header', async () => {
    session.token = 'tok'
    const fetch = okFetch()
    vi.stubGlobal('fetch', fetch)
    await postJson('/disruptions/interpret', {})
    const headers = fetch.mock.calls[0][1]!.headers as Record<string, string>
    expect(headers).toEqual({ 'Content-Type': 'application/json', Authorization: 'Bearer tok' })
  })

  it('sends nothing for a guest', async () => {
    const fetch = okFetch()
    vi.stubGlobal('fetch', fetch)
    await getJson('/places/search', { q: 'x' })
    expect(fetch.mock.calls[0][1]!.headers).toEqual({})
  })
})

describe('accessMessage', () => {
  it('words the guest limit and an expired login, and nothing else', () => {
    expect(accessMessage(new ApiError(429, 'x'))).toContain('로그인하면')
    expect(accessMessage(new ApiError(401, 'x'))).toContain('다시 로그인')
    expect(accessMessage(new ApiError(503, 'x'))).toBeNull()
    expect(accessMessage(new Error('network'))).toBeNull()
  })
})
