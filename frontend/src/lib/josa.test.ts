// A4 (review 2026-11-19): "메이지 신궁을(를)" -> pick the particle from the last syllable.
import { describe, expect, it } from 'vitest'
import { withJosa } from './josa'

describe('withJosa', () => {
  it('picks 을/를 by the final consonant', () => {
    expect(withJosa('메이지 신궁', '을/를')).toBe('메이지 신궁을')
    expect(withJosa('하라주쿠', '을/를')).toBe('하라주쿠를')
  })

  it('picks 으로/로, with ㄹ taking 로', () => {
    expect(withJosa('오모테산도', '으로/로')).toBe('오모테산도로')
    expect(withJosa('신주쿠역', '으로/로')).toBe('신주쿠역으로')
    expect(withJosa('시부야 스카이 전망대 홀', '으로/로')).toBe('시부야 스카이 전망대 홀로')
  })

  it('picks 이/가 and 은/는', () => {
    expect(withJosa('라멘', '이/가')).toBe('라멘이')
    expect(withJosa('카페', '은/는')).toBe('카페는')
  })

  it('reads through closing quotes and brackets', () => {
    expect(withJosa('“이자카야 저녁”', '으로/로')).toBe('“이자카야 저녁”으로')
    expect(withJosa('스카이 (예약)', '을/를')).toBe('스카이 (예약)을')
  })

  it('reads digits as spoken and falls back to both forms when it cannot tell', () => {
    expect(withJosa('2번 출구 3', '을/를')).toBe('2번 출구 3을')
    expect(withJosa('Shibuya Sky', '을/를')).toBe('Shibuya Sky을(를)')
  })
})
