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

// Sizes in CSS pixels. A piece must hold its label: the icon and time on one line, two lines of
// name under it (labels were cut off in narrow or low pieces, 2026-11-24). When the cut can't
// keep every piece that big, the quilt grows taller instead.
const MIN_W = 128
const MIN_H = 108
const SEAM_PX = 5 // left around each piece, where the denim ground shows like a seam
export const QUILT_WIDTH = 340 // about the map's width on a phone
const BASE_HEIGHT = 240
const MAX_HEIGHT = 640

/** Guillotine cut of a W x H box into n pieces no smaller than MIN_W x MIN_H, or null. */
function cut(n: number, rand: () => number, W: number, H: number): Rect[] | null {
  const rects: Rect[] = [{ x: 0, y: 0, w: W, h: H }]
  while (rects.length < n) {
    rects.sort((a, b) => b.w * b.h - a.w * a.h)
    let done = false
    for (let k = 0; k < rects.length && !done; k++) {
      const r = rects[k]
      const tries: ('x' | 'y')[] = r.w >= r.h ? ['x', 'y'] : ['y', 'x']
      for (const dir of tries) {
        const len = dir === 'x' ? r.w : r.h
        const min = dir === 'x' ? MIN_W : MIN_H
        const lo = Math.max(0.38, min / len)
        const hi = Math.min(0.62, 1 - min / len)
        if (lo > hi) continue
        const at = lo + rand() * (hi - lo)
        rects.splice(k, 1)
        if (dir === 'x') {
          const w1 = Math.round(r.w * at)
          rects.push({ ...r, w: w1 }, { ...r, x: r.x + w1, w: r.w - w1 })
        } else {
          const h1 = Math.round(r.h * at)
          rects.push({ ...r, h: h1 }, { ...r, y: r.y + h1, h: r.h - h1 })
        }
        done = true
        break
      }
    }
    if (!done) return null
  }
  // Reading order (rows by top, then left), so stops go left to right, top to bottom.
  return rects.sort((a, b) => a.y - b.y || a.x - b.x)
}

export type QuiltLayout = { pieces: Piece[]; height: number }

/** The quilt for one day: a piece per stop (up to 6), fabrics without repeats, and the height
 *  the map needs so every piece holds its label. A day with one or two stops gets two plain
 *  scraps more, so it still reads as a quilt; the stops take the biggest pieces. */
export function quiltLayout(n: number, key: string, width = QUILT_WIDTH): QuiltLayout {
  const stops = Math.max(0, Math.min(6, n))
  const count = Math.max(1, stops <= 2 ? stops + 2 : stops)
  for (let H = BASE_HEIGHT; ; H += 24) {
    const rand = seeded(key) // same key, same quilt, whatever height it ends up
    const fabrics = [...QUILT_FABRICS]
    for (let i = fabrics.length - 1; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1))
      ;[fabrics[i], fabrics[j]] = [fabrics[j], fabrics[i]]
    }
    const rects = cut(count, rand, width, H)
    if (!rects && H < MAX_HEIGHT) continue
    const cells = rects ?? [{ x: 0, y: 0, w: width, h: H }]
    const pct = (v: number, of: number) => (v / of) * 100
    const pieces = cells.map((r, i) => ({
      box: {
        left: pct(r.x + SEAM_PX, width),
        top: pct(r.y + SEAM_PX, H),
        width: pct(r.w - 2 * SEAM_PX, width),
        height: pct(r.h - 2 * SEAM_PX, H),
      },
      fabric: fabrics[i % fabrics.length],
      tilt: Math.round((rand() - 0.5) * 30),
      stop: null as number | null,
    }))
    return { pieces: assignStops(pieces, stops), height: H }
  }
}

/** Just the pieces (see quiltLayout). */
export function quilt(n: number, key: string): Piece[] {
  return quiltLayout(n, key).pieces
}

/** The name as the map shows it: "National Museum (체코 국립박물관)" → the Korean half, the list
 *  below keeps the full title. */
export function mapTitle(title: string): string {
  const m = /^(.+?)\s*\(([^)]+)\)\s*$/.exec(title.trim())
  if (!m) return title
  const hangul = /[가-힣]/
  if (hangul.test(m[2]) && !hangul.test(m[1])) return m[2]
  return m[1]
}

function assignStops(pieces: Piece[], stops: number): Piece[] {
  const biggest = [...pieces.keys()]
    .sort((a, b) => pieces[b].box.width * pieces[b].box.height - pieces[a].box.width * pieces[a].box.height)
    .slice(0, stops)
    .sort((a, b) => a - b) // back to reading order, so stops still go left to right
  return pieces.map((p, i) => ({ ...p, stop: biggest.includes(i) ? biggest.indexOf(i) : null }))
}

/** A seam two pieces share, in percent of the box: where the thread crosses from one to the next. */
export type Bridge = { x1: number; y1: number; x2: number; y2: number; across: 'x' | 'y' }

const GAP = 5 // percent: wider than any seam, narrower than any piece

/** The seam between two pieces if they touch, else null. Stitches cross it only there, so the
 *  thread joins pieces without running over them (a line through them hid labels, 2026-11-24). */
export function bridge(a: Piece, b: Piece): Bridge | null {
  const A = { l: a.box.left, t: a.box.top, r: a.box.left + a.box.width, b: a.box.top + a.box.height }
  const B = { l: b.box.left, t: b.box.top, r: b.box.left + b.box.width, b: b.box.top + b.box.height }
  const overlap = (s1: number, e1: number, s2: number, e2: number) => [Math.max(s1, s2), Math.min(e1, e2)]
  // side by side
  for (const [L, R] of [[A, B], [B, A]]) {
    const gap = R.l - L.r
    if (gap >= 0 && gap <= GAP) {
      const [s, e] = overlap(L.t, L.b, R.t, R.b)
      if (e - s > 6) return { x1: L.r, y1: (s + e) / 2, x2: R.l, y2: (s + e) / 2, across: 'x' }
    }
  }
  // one above the other
  for (const [T, U] of [[A, B], [B, A]]) {
    const gap = U.t - T.b
    if (gap >= 0 && gap <= GAP) {
      const [s, e] = overlap(T.l, T.r, U.l, U.r)
      if (e - s > 6) return { x1: (s + e) / 2, y1: T.b, x2: (s + e) / 2, y2: U.t, across: 'y' }
    }
  }
  return null
}

/** Seams to stitch across, one per pair of consecutive stops that touch. */
export function bridges(pieces: Piece[]): Bridge[] {
  const byStop = pieces.filter((p) => p.stop !== null).sort((a, b) => a.stop! - b.stop!)
  const out: Bridge[] = []
  for (let i = 1; i < byStop.length; i++) {
    const s = bridge(byStop[i - 1], byStop[i])
    if (s) out.push(s)
  }
  return out
}
