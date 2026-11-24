import aquarium from '../assets/patches/place-aquarium.svg'
import beach from '../assets/patches/place-beach.svg'
import bookstore from '../assets/patches/place-bookstore.svg'
import bridge from '../assets/patches/place-bridge.svg'
import cafe from '../assets/patches/place-cafe.svg'
import castle from '../assets/patches/place-castle.svg'
import church from '../assets/patches/place-church.svg'
import dessert from '../assets/patches/place-dessert.svg'
import drugstore from '../assets/patches/place-drugstore.svg'
import fashion from '../assets/patches/place-fashion.svg'
import food from '../assets/patches/place-food.svg'
import bar from '../assets/patches/place-izakaya.svg'
import mall from '../assets/patches/place-mall.svg'
import market from '../assets/patches/place-market.svg'
import monument from '../assets/patches/place-monument.svg'
import museum from '../assets/patches/place-museum.svg'
import nature from '../assets/patches/place-nature.svg'
import viewpoint from '../assets/patches/place-nightview.svg'
import spa from '../assets/patches/place-onsen.svg'
import park from '../assets/patches/place-park.svg'
import shopping from '../assets/patches/place-shopping.svg'
import worship from '../assets/patches/place-shrine.svg'
import temple from '../assets/patches/place-temple.svg'
import sight from '../assets/patches/place-sight.svg'
import souvenir from '../assets/patches/place-souvenir.svg'
import square from '../assets/patches/place-square.svg'
import lodging from '../assets/patches/place-stay.svg'
import themePark from '../assets/patches/place-themepark.svg'
import tower from '../assets/patches/place-tower.svg'
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
  bridge,
  castle,
  square,
  tower,
  park,
  aquarium,
  dessert,
  monument,
  souvenir,
  bookstore,
  fashion,
  drugstore,
}

export const DEFAULT_ICON = sight

// Trips parsed before "church" / "temple" existed (2026-11-24) say "worship" for all of them, and a
// torii on a cathedral is wrong: the title decides, in the languages travellers write.
const CHURCH_WORDS = /성당|교회|예배당|cathedral|church|chapel|basilica|kirche|église|eglise|chiesa|duomo|kostel|katedr|教会|大聖堂|聖堂/i
const TEMPLE_WORDS = /사찰|temple|pagoda|寺|tempel|\bwat\b|-ji\b/i

// Trips parsed before these kinds existed (2026-11-25) have no patch for a bridge, a castle or a
// bookstore, so they all got the camera. The title decides, first match wins (the order matters:
// "대성당" is a church, not a castle).
const TITLE_KINDS: [RegExp, PatchKind][] = [
  [CHURCH_WORDS, 'church'],
  [/수족관|아쿠아리움|동물원|aquarium|\bzoo\b|水族館|動物園/i, 'aquarium'],
  [/드럭스토어|약국|돈키호테|올리브영|drugstore|pharmacy|don quijote|donki|화장품|cosmetic/i, 'drugstore'],
  [/기념품|souvenir|gift shop|お土産/i, 'souvenir'],
  [/서점|책방|bookstore|bookshop|librairie|書店/i, 'bookstore'],
  [/옷가게|편집숍|부티크|boutique|유니클로|uniqlo|\bzara\b|빈티지 ?숍|vintage shop/i, 'fashion'],
  [/디저트|베이커리|빵집|케이크|아이스크림|젤라또|bakery|dessert|gelato|p[aâ]tisserie|ice cream/i, 'dessert'],
  [/다리|대교|카를교|bridge|\bmost\b|brücke|\bpont\b|ponte|橋/i, 'bridge'],
  [/궁전|왕궁|고궁|성곽|(?:^|[가-힣\s])성(?![가-힣])|castle|palace|palais|palazzo|schloss|\bburg\b|\bhrad|château|城/i, 'castle'],
  [/광장|구시가지|올드 ?타운|old town|square|plaza|piazza|platz|náměstí|namesti/i, 'square'],
  [/기념비|동상|개선문|monument|memorial|statue|triumph/i, 'monument'],
  [/타워|시계탑|tower|\bturm\b|věž|塔/i, 'tower'],
  [/공원|정원|가든|\bpark\b|garden|jardin|giardino|zahrada|庭園|公園/i, 'park'],
]

// A café by its name, in the words travellers write ("Café Savoy" came back as a meal with the
// izakaya lantern, 2026-11-25).
const CAFE_WORDS = /카페|커피|café|\bcafe\b|caffè|caffe\b|coffee|kavárna|kavarna|kaffee|喫茶|咖啡/i

function titleKind(title: string | undefined): PatchKind | null {
  if (!title) return null
  for (const [re, kind] of TITLE_KINDS) if (re.test(title)) return kind
  return null
}

function worshipIcon(title: string | undefined): string {
  if (title && CHURCH_WORDS.test(title)) return church
  if (title && TEMPLE_WORDS.test(title)) return temple
  return worship
}

/** The item's place patch if it has one, else its category's, else the default. Unknown values
 *  (an older or newer app version) fall through instead of breaking the image. */
export function itemIcon(item: { category: string; patch?: string | null; title?: string }): string {
  // A café is a café even when the parser called it a bar ("Café Louvre" got the izakaya lantern);
  // a bakery or a gelato shop the parser filed under cafe keeps its cake.
  const cafeByName = !!item.title && CAFE_WORDS.test(item.title)
  if ((item.category === 'cafe' || cafeByName) && item.patch !== 'museum' && item.patch !== 'viewpoint') {
    return item.patch === 'dessert' || titleKind(item.title) === 'dessert' ? dessert : cafe
  }
  if (item.patch === 'worship') return worshipIcon(item.title)
  if (item.patch && Object.hasOwn(PATCH_ICON, item.patch)) return PATCH_ICON[item.patch as PatchKind]
  const byTitle = titleKind(item.title)
  if (byTitle) return PATCH_ICON[byTitle]
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
