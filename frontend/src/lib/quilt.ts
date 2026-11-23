// The fabric "map" on Main as a crazy quilt (decision 2026-11-24): every day gets its own cut
// of the box and its own scraps of cloth, chosen by a seed from the trip and the date, so the
// same day always looks the same and no two days look alike. It used to be four hand-placed
// rectangles with the same four fabrics every day.

/** Every cloth in styles/patterns.css that reads well under a label (the denim ground is not). */
export const QUILT_FABRICS = [
  'check',
  'stripe',
  'dot',
  'hempweave',
  'plaid',
  'redfloral',
  'butterfloral',
  'gingham-rose',
  'gingham-sky',
  'ticking',
  'pinstripe',
  'polka-mustard',
  'ditsy-sage',
  'corduroy',
  'chambray',
  'tartan',
  'seersucker',
  'lace-dot',
] as const
export type Fabric = (typeof QUILT_FABRICS)[number]

export type Piece = {
  /** Where the piece sits, in percent of the box. Clean rectangles: hand-cut wobble read as
   *  careless (2026-11-24), the variety comes from the cut and the cloth. */
  box: { left: number; top: number; width: number; height: number }
  fabric: Fabric
  /** Small tilt of the cloth's grain, in degrees. */
  tilt: number
  /** Which stop of the day this piece carries (0-based), or null for a plain scrap. */
  stop: number | null
}

/** Same string, same numbers (FNV-1a then mulberry32). */
export function seeded(key: string): () => number {
  let h = 2166136261
  for (let i = 0; i < key.length; i++) h = Math.imul(h ^ key.charCodeAt(i), 16777619)
  let a = h >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

type Rect = { x: number; y: number; w: number; h: number }

/** Cut the box into `n` rectangles: always cut the biggest one across its longer side, at a
 *  random place between 38% and 62%, so pieces stay big enough for a label. Reading order. */
function cut(n: number, rand: () => number): Rect[] {
  // The box is 100 x 100 percent but drawn about 1.6:1 wide, so "longer side" compares w*1.6 to h.
  let rects: Rect[] = [{ x: 0, y: 0, w: 100, h: 100 }]
  while (rects.length < n) {
    rects.sort((a, b) => b.w * b.h - a.w * a.h)
    const r = rects.shift()!
    const at = 0.4 + rand() * 0.2
    // Cut across the longer side, unless that leaves a sliver too narrow for a label
    // ("츠키지" in a 70px strip, 2026-11-24): then cut the other way.
    let across = r.w * ASPECT >= r.h
    if (across && r.w * 0.4 < MIN_W) across = false
    else if (!across && r.h * 0.4 < MIN_H) across = true
    if (across) {
      const w1 = r.w * at
      rects.push({ ...r, w: w1 }, { ...r, x: r.x + w1, w: r.w - w1 })
    } else {
      const h1 = r.h * at
      rects.push({ ...r, h: h1 }, { ...r, y: r.y + h1, h: r.h - h1 })
    }
  }
  // Reading order (rows by top, then left), so the route goes left to right, top to bottom.
  return rects.sort((a, b) => Math.round(a.y / 20) - Math.round(b.y / 20) || a.x - b.x)
}

const ASPECT = 1.6 // the map box is about this much wider than tall
const MIN_W = 26 // percent: narrowest piece that still holds a two-line label
const MIN_H = 30
const SEAM = 1.4 // percent left between pieces, where the denim ground shows like a seam

/** The quilt for one day: a piece per stop (up to 6), fabrics without repeats. A day with one
 *  or two stops gets two plain scraps more, so it still reads as a quilt, not one big cloth;
 *  the stops take the biggest pieces. */
export function quilt(n: number, key: string): Piece[] {
  const rand = seeded(key)
  const stops = Math.max(0, Math.min(6, n))
  const count = Math.max(1, stops <= 2 ? stops + 2 : stops)
  const fabrics = [...QUILT_FABRICS]
  for (let i = fabrics.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1))
    ;[fabrics[i], fabrics[j]] = [fabrics[j], fabrics[i]]
  }
  const pieces = cut(count, rand).map((r, i) => {
    const l = r.x + SEAM
    const t = r.y + SEAM * ASPECT // a vertical percent is shorter on screen than a horizontal one
    return {
      box: { left: l, top: t, width: r.w - 2 * SEAM, height: r.h - 2 * SEAM * ASPECT },
      fabric: fabrics[i % fabrics.length],
      tilt: Math.round((rand() - 0.5) * 30),
      stop: null as number | null,
    }
  })
  return assignStops(pieces, stops)
}

function assignStops(pieces: Piece[], stops: number): Piece[] {
  const biggest = [...pieces.keys()]
    .sort((a, b) => pieces[b].box.width * pieces[b].box.height - pieces[a].box.width * pieces[a].box.height)
    .slice(0, stops)
    .sort((a, b) => a - b) // back to reading order, so stops still go left to right
  return pieces.map((p, i) => ({ ...p, stop: biggest.includes(i) ? biggest.indexOf(i) : null }))
}
