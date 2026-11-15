import cafe from '../assets/patches/place-cafe.svg'
import food from '../assets/patches/place-food.svg'
import market from '../assets/patches/place-market.svg'
import nightview from '../assets/patches/place-nightview.svg'
import shopping from '../assets/patches/place-shopping.svg'
import shrine from '../assets/patches/place-shrine.svg'
import sight from '../assets/patches/place-sight.svg'
import type { PlaceIcon } from '../mocks/draftItinerary'

export const PLACE_ICONS: Record<PlaceIcon, string> = { food, market, nightview, shopping, shrine, sight }

// Engine activity category -> icon, for screens that only have engine data (no mock icon key).
export const CATEGORY_ICON: Record<string, string> = {
  meal: food,
  sightseeing: sight,
  shopping,
  cafe,
}
export const DEFAULT_ICON = sight
