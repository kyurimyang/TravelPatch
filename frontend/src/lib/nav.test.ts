import { describe, expect, it } from 'vitest'
import { loginPath, safeNext } from './nav'

describe('safeNext', () => {
  it('keeps paths inside the app', () => {
    expect(safeNext('/settings')).toBe('/settings')
    expect(safeNext('/recover?x=1')).toBe('/recover?x=1')
  })
  it('sends anything else home', () => {
    for (const bad of [null, undefined, '', 'settings', '//evil.com', '/\\evil.com', 'https://evil.com', '/login', '/signup?next=/x']) {
      expect(safeNext(bad)).toBe('/')
    }
  })
})

describe('loginPath', () => {
  it('carries the destination', () => {
    expect(loginPath('/settings/withdraw')).toBe('/login?next=%2Fsettings%2Fwithdraw')
    expect(loginPath('/trips', '/signup')).toBe('/signup?next=%2Ftrips')
  })
  it('leaves home out of the URL', () => {
    expect(loginPath('/')).toBe('/login')
    expect(loginPath('/login?next=/x')).toBe('/login')
  })
})
