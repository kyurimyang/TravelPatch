import type { Blocker } from '../api/types'
import { formatTime } from '../lib/time'

// Why no plan exists. The backend only names causes it is sure of; an empty list means "unknown".
function describe(blocker: Blocker, title: string): string {
  switch (blocker.kind) {
    case 'reserved_in_past':
      return `${title}: 예약 시각${
        blocker.blocking_time != null ? `(${formatTime(blocker.blocking_time)})` : ''
      }이 이미 지나서 맞출 수 없어요`
    case 'reserved_in_rain':
      return `${title}: 비 오는 시간에 잡힌 야외 예약이라 옮길 수 없어요`
    case 'extension_blocked':
      return `${title}: 운영 시간 때문에 ${blocker.max_extra_minutes ?? 0}분까지만 늘릴 수 있어요`
    case 'closed_no_substitute':
      return `${title}: 문을 닫았는데 ‘꼭’이라 뺄 수 없고, 근처에 그 시간에 여는 비슷한 곳을 찾지 못했어요`
    case 'reservations_clash':
      return `${title}: 앞 예약이 끝나고 이동하면 예약 시각${
        blocker.blocking_time != null ? `(${formatTime(blocker.blocking_time)})` : ''
      }에 닿을 수 없어요`
    case 'meal_out_of_reach':
      return `${title}: ‘꼭’ 식사인데${
        blocker.blocking_time != null ? ` ${formatTime(blocker.blocking_time)}까지` : ''
      } 시작할 수 없어요`
  }
}

interface Props {
  blockers: Blocker[]
  titleOf: ReadonlyMap<string, string>
}

export function BlockerList({ blockers, titleOf }: Props) {
  return (
    <section>
      <h2>이 사건으로는 가능한 일정이 없어요</h2>
      {blockers.length === 0 ? (
        <p>원인을 특정하지 못했어요.</p>
      ) : (
        <ul>
          {blockers.map((b) => (
            <li key={`${b.kind}-${b.activity_id}`}>
              {describe(b, titleOf.get(b.activity_id) ?? b.activity_id)}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
