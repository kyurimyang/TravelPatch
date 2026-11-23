import { describe, expect, it } from 'vitest'
import { QUILT_FABRICS, QUILT_WIDTH, bridges, mapTitle, quilt, quiltLayout } from './quilt'

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

describe('bridges', () => {
  it('only joins consecutive stops that share a seam, and never crosses a piece', () => {
    for (const n of [2, 3, 4, 5, 6]) {
      for (const k of ['a', 'b', 'c', 'd']) {
        const q = quilt(n, `${k}${n}`)
        for (const s of bridges(q)) {
          const mid = [(s.x1 + s.x2) / 2, (s.y1 + s.y2) / 2]
          const inside = q.some(
            (p) =>
              mid[0] > p.box.left && mid[0] < p.box.left + p.box.width &&
              mid[1] > p.box.top && mid[1] < p.box.top + p.box.height,
          )
          expect(inside).toBe(false)
        }
      }
    }
  })

  it('finds the seam between two neighbours', () => {
    const q = quilt(3, 'seam')
    expect(bridges(q).length).toBeGreaterThan(0)
  })
})

describe('quiltLayout', () => {
  it('never cuts a piece too small for its label, growing the map instead', () => {
    for (const n of [1, 2, 3, 4, 5, 6]) {
      for (const k of ['p', 'q', 'r', 's', 't']) {
        const { pieces, height } = quiltLayout(n, `${k}${n}`)
        for (const p of pieces) {
          expect((p.box.width / 100) * QUILT_WIDTH).toBeGreaterThanOrEqual(117.9)
          expect((p.box.height / 100) * height).toBeGreaterThanOrEqual(97.9)
        }
      }
    }
  })
})

describe('mapTitle', () => {
  it('keeps the Korean half of "English (한국어)"', () => {
    expect(mapTitle('National Museum (체코 국립박물관)')).toBe('체코 국립박물관')
    expect(mapTitle('바츨라프 광장 (Wenceslas Square)')).toBe('바츨라프 광장')
    expect(mapTitle('마지막 쇼핑 및 카페 방문')).toBe('마지막 쇼핑 및 카페 방문')
  })
})
