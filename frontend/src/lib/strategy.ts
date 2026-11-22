// Display names for backend/app/engine/presets.py strategy names. Unknown names fall back to the raw name.
const STRATEGY_LABEL: Record<string, string> = {
  balanced: '균형',
  sightseeing: '관광 보존',
  low_travel: '이동 최소화',
  relaxed: '여유 보존',
  food: '음식 보존',
  reservation: '예약 보존',
}

export function strategyLabel(name: string): string {
  return STRATEGY_LABEL[name] ?? name
}
