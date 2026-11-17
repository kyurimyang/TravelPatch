import cafe from '../assets/patches/place-cafe.svg'
import food from '../assets/patches/place-food.svg'
import shopping from '../assets/patches/place-shopping.svg'
import sight from '../assets/patches/place-sight.svg'

// Activity category -> patch icon.
export const CATEGORY_ICON: Record<string, string> = {
  meal: food,
  sightseeing: sight,
  shopping,
  cafe,
}
export const DEFAULT_ICON = sight
