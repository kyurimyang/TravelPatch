// The minutes between neighbouring stops of a day, for the chips shown between rows.
// The server's travel table is undirected and has a pair for every two places; a day only
// ever shows the pairs it actually walks, in the order it walks them.
import type { TravelTime } from '../api/types'

export type Leg = { from: string; to: string; minutes: number; source: TravelTime['source'] }

const key = (a: string, b: string) => (a < b ? `${a}\u0000${b}` : `${b}\u0000${a}`)

/** One leg per neighbouring pair of `stops`. A pair missing from the table gets no leg: the
 *  chip is never filled with a made-up number (CLAUDE.md invariant 8). */
export function legsAlong(stops: readonly string[], travel: readonly TravelTime[]): Leg[] {
  const byPair = new Map(travel.map((t) => [key(t.a, t.b), t]))
  const legs: Leg[] = []
  for (let i = 0; i + 1 < stops.length; i++) {
    const hit = byPair.get(key(stops[i], stops[i + 1]))
    if (hit) legs.push({ from: stops[i], to: stops[i + 1], minutes: hit.minutes, source: hit.source })
  }
  return legs
}

/** The leg that arrives at each stop, by stop id. A row shows the way *into* it. */
export function legIntoEach(stops: readonly string[], travel: readonly TravelTime[]): Map<string, Leg> {
  return new Map(legsAlong(stops, travel).map((leg) => [leg.to, leg]))
}
