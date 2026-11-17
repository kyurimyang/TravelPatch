import type { Category, TripItem } from '../store/trip'
import type { Tier } from './tier'
import { CATEGORY_ICON, DEFAULT_ICON } from './placeIcons'

export const CATEGORY_LABEL: Record<Category, string> = {
  meal: '식사',
  sightseeing: '관광',
  shopping: '쇼핑',
  cafe: '카페',
  transport: '이동',
  other: '기타',
}

export function categoryIcon(category: string): string {
  return CATEGORY_ICON[category] ?? DEFAULT_ICON
}

/** The tier a new item starts with until the LLM step exists: reserved -> must, else nice
 * (decisions 2026-11-17). Grade marks any other choice as the user's own. */
export function defaultTier(item: Pick<TripItem, 'reservationTime'>): Tier {
  return item.reservationTime != null ? 'must' : 'nice'
}
