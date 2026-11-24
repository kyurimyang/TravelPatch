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

  it('finds the new kinds from the title on trips parsed before they existed', () => {
    const t = (title: string, category = 'sightseeing') => itemIcon({ category, patch: null, title })
    expect(t('카를교 (Charles Bridge)')).toBe(PATCH_ICON.bridge)
    expect(t('프라하 성')).toBe(PATCH_ICON.castle)
    expect(t('성 비투스 대성당')).toBe(PATCH_ICON.church) // 성 ... 성당 is a church, not a castle
    expect(t('Old Town Square (구시가지 광장)')).toBe(PATCH_ICON.square)
    expect(t('도쿄타워')).toBe(PATCH_ICON.tower)
    expect(t('Letná Park')).toBe(PATCH_ICON.park)
    expect(t('카이유칸 수족관')).toBe(PATCH_ICON.aquarium)
    expect(t('돈키호테 시부야점', 'shopping')).toBe(PATCH_ICON.drugstore)
    expect(t('기념품 쇼핑', 'shopping')).toBe(PATCH_ICON.souvenir)
    expect(t('츠타야 서점', 'shopping')).toBe(PATCH_ICON.bookstore)
    expect(t('Gelato Fatamorgana', 'cafe')).toBe(PATCH_ICON.dessert)
    expect(t('Café Louvre', 'cafe')).toBe(itemIcon({ category: 'cafe' }))
    expect(t('오모테산도 산책')).toBe(itemIcon({ category: 'sightseeing' })) // nothing known: the camera
  })
})
