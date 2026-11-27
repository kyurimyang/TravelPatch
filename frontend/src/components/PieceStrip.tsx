import type { RecoveryChange } from '../api/types'
import './PieceStrip.css'

// The day as a strip of fabric pieces, in order: kept pieces plain linen, changed ones a patch of
// cloth (the op decides which), a dropped one a hole with a loose red thread. Replaces the two
// "바뀌는 조각 / 그대로인 조각" stat boxes, which read like a dashboard (2026-11-24).
export function PieceStrip({ changes, titleOf }: { changes: RecoveryChange[]; titleOf: (id: string) => string }) {
  const ordered = [...changes].sort(
    (a, b) => (a.after ?? a.before ?? { start: 0 }).start - (b.after ?? b.before ?? { start: 0 }).start,
  )
  const changed = changes.filter((c) => c.op !== 'keep').length
  const toCheck = changes.filter((c) => c.needs_check).length
  return (
    <div className="piece-strip">
      <ol aria-label="오늘의 조각">
        {ordered.map((c) => (
          <li key={c.activity_id} data-op={c.op} title={titleOf(c.activity_id)}>
            <span className="sr-only">{titleOf(c.activity_id)}</span>
          </li>
        ))}
      </ol>
      <p>
        {changed > 0 ? (
          <>
            조각 <b>{changed}개</b>를 덧대
            {changes.length > changed ? `고, ${changes.length - changed}개는 그대로 둬요` : '요'}
          </>
        ) : (
          <>조각을 그대로 두고 이어 붙여요</>
        )}
      </p>
      {toCheck > 0 && (
        <p className="piece-strip__check">
          <span aria-hidden="true" />
          {toCheck}곳은 미리 알 수 없는 게 있어요. 가서 한 번 확인해 주세요
        </p>
      )}
    </div>
  )
}
