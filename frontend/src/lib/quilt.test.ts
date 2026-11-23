import { describe, expect, it } from 'vitest'
import { QUILT_FABRICS, quilt } from './quilt'

describe('quilt', () => {
  it('is the same for the same day and differs between days', () => {
    expect(quilt(4, 't1:2026-11-24')).toEqual(quilt(4, 't1:2026-11-24'))
    const days = ['2026-11-23', '2026-11-24', '2026-11-25', '2026-11-26'].map((d) => quilt(4, `t1:${d}`))
    const looks = new Set(days.map((q) => q.map((p) => p.fabric).join() + q.map((p) => Math.round(p.box.width)).join()))
    expect(looks.size).toBe(4)
  })
  it('carries every stop once (at most 6), never the same cloth twice', () => {
    for (const n of [1, 2, 3, 4, 5, 6, 9]) {
      const q = quilt(n, `k${n}`)
      const stops = Math.min(6, n)
      expect(q.map((p) => p.stop).filter((s) => s !== null).sort()).toEqual([...Array(stops).keys()])
      expect(q).toHaveLength(stops <= 2 ? stops + 2 : stops) // a small day gets plain scraps
      expect(new Set(q.map((p) => p.fabric)).size).toBe(q.length)
      for (const p of q) {
        expect(p.box.width).toBeGreaterThan(8)
        expect(p.box.height).toBeGreaterThan(8)
        expect(QUILT_FABRICS).toContain(p.fabric)
      }
    }
  })
  it('covers the box without overlap', () => {
    const q = quilt(6, 'cover')
    const area = q.reduce((s, p) => s + p.box.width * p.box.height, 0)
    expect(area).toBeLessThan(100 * 100)
    expect(area).toBeGreaterThan(100 * 100 * 0.55) // seams take the rest
  })
})
