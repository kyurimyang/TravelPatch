// Same three values as the backend `tier` enum (CLAUDE.md 5절): must (5) / nice (3) / optional (1).
// Hand-written for now; replace with the generated API type when the preferences API exists.
export type Tier = 'must' | 'nice' | 'optional'

export const TIERS: { value: Tier; label: string }[] = [
  { value: 'must', label: '꼭' },
  { value: 'nice', label: '좋음' },
  { value: 'optional', label: '선택' },
]
