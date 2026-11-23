import beach from '../assets/patches/place-beach.svg'
import cafe from '../assets/patches/place-cafe.svg'
import church from '../assets/patches/place-church.svg'
import food from '../assets/patches/place-food.svg'
import bar from '../assets/patches/place-izakaya.svg'
import mall from '../assets/patches/place-mall.svg'
import market from '../assets/patches/place-market.svg'
import museum from '../assets/patches/place-museum.svg'
import nature from '../assets/patches/place-nature.svg'
import viewpoint from '../assets/patches/place-nightview.svg'
import spa from '../assets/patches/place-onsen.svg'
import shopping from '../assets/patches/place-shopping.svg'
import worship from '../assets/patches/place-shrine.svg'
import temple from '../assets/patches/place-temple.svg'
import sight from '../assets/patches/place-sight.svg'
import lodging from '../assets/patches/place-stay.svg'
import themePark from '../assets/patches/place-themepark.svg'
import transport from '../assets/patches/place-transport.svg'
import venue from '../assets/patches/place-venue.svg'
import type { Category, PatchKind } from '../store/trip'

// Activity category -> patch picture. Used when an item has no `patch` kind.
export const CATEGORY_ICON: Record<Category, string> = {
  meal: food,
  sightseeing: sight,
  shopping,
  cafe,
  transport,
  other: sight,
}

// Place kind the parser chose (backend PatchKind) -> patch picture. Record<PatchKind, ...> makes
// a kind added on the server without a picture here a type error after `npm run gen:api`.
export const PATCH_ICON: Record<PatchKind, string> = {
  worship,
  church,
  temple,
  museum,
  viewpoint,
  bar,
  market,
  nature,
  spa,
  beach,
  lodging,
  theme_park: themePark,
  venue,
  mall,
}

export const DEFAULT_ICON = sight

// Trips parsed before "church" / "temple" existed (2026-11-24) say "worship" for all of them, and a
// torii on a cathedral is wrong: the title decides, in the languages travellers write.
const CHURCH_WORDS = /성당|교회|예배당|cathedral|church|chapel|basilica|kirche|église|eglise|chiesa|duomo|kostel|katedr|教会|大聖堂|聖堂/i
const TEMPLE_WORDS = /사찰|temple|pagoda|寺|tempel|\bwat\b|-ji\b/i

function worshipIcon(title: string | undefined): string {
  if (title && CHURCH_WORDS.test(title)) return church
  if (title && TEMPLE_WORDS.test(title)) return temple
  return worship
}

/** The item's place patch if it has one, else its category's, else the default. Unknown values
 *  (an older or newer app version) fall through instead of breaking the image. */
export function itemIcon(item: { category: string; patch?: string | null; title?: string }): string {
  // A café is a café even when the parser called it a bar ("Café Louvre" got the izakaya lantern).
  if (item.category === 'cafe' && item.patch !== 'museum' && item.patch !== 'viewpoint') return cafe
  if (item.patch === 'worship') return worshipIcon(item.title)
  if (item.patch && Object.hasOwn(PATCH_ICON, item.patch)) return PATCH_ICON[item.patch as PatchKind]
  if (Object.hasOwn(CATEGORY_ICON, item.category)) return CATEGORY_ICON[item.category as Category]
  return DEFAULT_ICON
}

/** Picture per engine activity id. Activity ids are the trip's item ids, so an item found in the
 *  trip gives its patch kind; anything else (a demo day, a searched substitute) uses its category. */
export function iconsById(
  trip: { days: { items: { id: string; category: string; patch?: string | null; title?: string }[] }[] } | null,
  activities: { id: string; category: string; title?: string }[],
): Map<string, string> {
  const items = new Map((trip?.days ?? []).flatMap((d) => d.items).map((it) => [it.id, it]))
  return new Map(activities.map((a) => [a.id, itemIcon(items.get(a.id) ?? a)]))
}
