import { describe, expect, it } from 'vitest'
import { PATCH_ICON, itemIcon } from './placeIcons'

describe('itemIcon', () => {
  it('gives a café the cup, even when the parser called it a bar', () => {
    expect(itemIcon({ category: 'cafe', patch: 'bar', title: 'Café Louvre' })).toBe(
      itemIcon({ category: 'cafe' }),
    )
  })

  it('tells a cathedral from a shrine on older "worship" trips', () => {
    expect(itemIcon({ category: 'sightseeing', patch: 'worship', title: '성 비투스 대성당' })).toBe(PATCH_ICON.church)
    expect(itemIcon({ category: 'sightseeing', patch: 'worship', title: 'St. Vitus Cathedral' })).toBe(PATCH_ICON.church)
    expect(itemIcon({ category: 'sightseeing', patch: 'worship', title: 'Kiyomizu-dera 清水寺' })).toBe(PATCH_ICON.temple)
    expect(itemIcon({ category: 'sightseeing', patch: 'worship', title: 'Fushimi Inari' })).toBe(PATCH_ICON.worship)
  })

  it('uses the new kinds directly', () => {
    expect(itemIcon({ category: 'sightseeing', patch: 'church' })).toBe(PATCH_ICON.church)
    expect(itemIcon({ category: 'sightseeing', patch: 'temple' })).toBe(PATCH_ICON.temple)
  })
})
