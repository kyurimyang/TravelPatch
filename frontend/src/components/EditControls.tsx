// The controls only the edit screen has (/trips/:id/edit): a locked day's notice, renaming and
// removing a piece, and adding one. The screen applies the changes (lib/tripEdit).
import { useState } from 'react'
import { CATEGORY_LABEL } from '../lib/category'
import { MAX_DAY_ITEMS } from '../lib/recovery'
import type { DayLock } from '../lib/tripEdit'
import type { Category, TripItem } from '../store/trip'
import { TimeEditor } from './TimeEditor'
import './EditControls.css'

export function DayLockNotice({ lock, patches, onUnpatch }: { lock: DayLock; patches: number; onUnpatch: () => void }) {
  const [asking, setAsking] = useState(false)
  if (lock === 'past') {
    return (
      <div className="edit-lock tp-fabric">
        <b>지난 날은 고칠 수 없어요</b>
        <span>여행의 기록으로 그대로 남겨 둬요.</span>
      </div>
    )
  }
  return (
    <div className="edit-lock tp-fabric">
      <b>패치 {patches}개를 덧댄 날이라 잠겨 있어요</b>
      <span>패치는 원래 계획을 기준으로 하기 때문에, 고치려면 먼저 풀어야 해요.</span>
      {asking ? (
        <div className="edit-lock__confirm" role="alert">
          <span>이날 패치를 모두 풀고 원래 계획으로 되돌릴까요? 패치 기록은 지워져요.</span>
          <button type="button" className="edit-danger" onClick={onUnpatch}>
            패치 풀기
          </button>
          <button type="button" onClick={() => setAsking(false)}>
            그대로 두기
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => setAsking(true)}>
          패치 풀고 고치기
        </button>
      )}
    </div>
  )
}

export function ItemTools({ item, onRename, onRemove }: { item: TripItem; onRename: (title: string) => void; onRemove: () => void }) {
  const [mode, setMode] = useState<'idle' | 'rename' | 'remove'>('idle')
  const [title, setTitle] = useState(item.title)

  if (mode === 'rename') {
    return (
      <form
        className="edit-tools"
        onSubmit={(e) => {
          e.preventDefault()
          if (!title.trim()) return
          onRename(title.trim())
          setMode('idle')
        }}
      >
        <input aria-label="조각 이름" maxLength={80} value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
        <button type="submit" disabled={!title.trim()}>
          저장
        </button>
        <button type="button" onClick={() => setMode('idle')}>
          취소
        </button>
      </form>
    )
  }
  if (mode === 'remove') {
    return (
      <div className="edit-tools" role="alert">
        <span>이 조각을 일정에서 뺄까요?</span>
        <button type="button" className="edit-danger" onClick={onRemove}>
          빼기
        </button>
        <button type="button" onClick={() => setMode('idle')}>
          그대로 두기
        </button>
      </div>
    )
  }
  return (
    <div className="edit-tools">
      <button
        type="button"
        onClick={() => {
          setTitle(item.title)
          setMode('rename')
        }}
      >
        이름 바꾸기
      </button>
      <button type="button" onClick={() => setMode('remove')}>
        이 조각 빼기
      </button>
    </div>
  )
}

/** A new piece: the user's words, kind and times. Its place is picked on its card afterwards
 *  (nothing is searched by the title, decision 2026-11-23). */
export function AddItem({ count, onAdd }: { count: number; onAdd: (item: TripItem) => void }) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState<Category>('sightseeing')

  if (count >= MAX_DAY_ITEMS) {
    return <p className="confirm__hint">하루에는 조각을 {MAX_DAY_ITEMS}개까지 둘 수 있어요.</p>
  }
  if (!open) {
    return (
      <button type="button" className="tp-btn-quiet" onClick={() => setOpen(true)}>
        조각 추가
      </button>
    )
  }
  return (
    <div className="edit-add tp-fabric">
      <label>
        <span>이름</span>
        <input maxLength={80} placeholder="예: 우에노 공원 산책" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
      </label>
      <label>
        <span>종류</span>
        <select value={category} onChange={(e) => setCategory(e.target.value as Category)}>
          {(Object.keys(CATEGORY_LABEL) as Category[]).map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABEL[c]}
            </option>
          ))}
        </select>
      </label>
      {!title.trim() && <p className="confirm__hint">이름과 시각을 적으면 추가할 수 있어요.</p>}
      <TimeEditor
        idPrefix="add-item"
        start={null}
        end={null}
        saveLabel="추가"
        onCancel={() => setOpen(false)}
        onSave={(start, end) => {
          if (!title.trim()) return
          onAdd({
            id: `u-${crypto.randomUUID().slice(0, 8)}`,
            title: title.trim(),
            category,
            start,
            end,
            durationEstimated: false,
            reservationTime: null,
            note: null,
            placeId: null,
            tier: 'nice',
          })
          setTitle('')
          setOpen(false)
        }}
      />
    </div>
  )
}
