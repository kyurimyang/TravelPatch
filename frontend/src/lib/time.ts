// Minutes since midnight -> "HH:MM".
export function formatTime(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

export function formatSlot(start: number, end: number): string {
  return `${formatTime(start)}–${formatTime(end)}`
}

// ISO date "2026-10-08" -> "10월 8일 목요일". Read as UTC so the viewer's own zone never shifts the day.
export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat('ko-KR', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
    timeZone: 'UTC',
  }).format(new Date(`${iso}T00:00:00Z`))
}

// "2026-10-07".."2026-10-09" -> "2박 3일"; one day -> "당일치기" (not "0박 1일").
export function tripLength(startIso: string, endIso: string): string {
  const nights = Math.round((Date.parse(endIso) - Date.parse(startIso)) / 86_400_000)
  return nights <= 0 ? '당일치기' : `${nights}박 ${nights + 1}일`
}

// "HH:MM" (what <input type="time"> gives) -> minutes since midnight; null for empty or bad text.
export function parseTime(text: string): number | null {
  const m = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(text)
  return m ? Number(m[1]) * 60 + Number(m[2]) : null
}
