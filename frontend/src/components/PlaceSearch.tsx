import { useState } from 'react'
import { ApiError } from '../api/http'
import { searchPlaces } from '../api/places'
import type { PlaceOption } from '../api/types'
import './PlaceSearch.css'

type Props = {
  /** id of the text input, for an outside <label htmlFor>. */
  inputId: string
  city: string
  placeholder?: string
  /** The place picked so far, shown with a "바꾸기" button. */
  picked: PlaceOption | null
  /** `query` = the words the user typed: the trip keeps those, not Google's name. */
  onPick: (place: PlaceOption, query: string) => void
}

type Phase =
  | { kind: 'idle' }
  | { kind: 'searching' }
  | { kind: 'results'; options: PlaceOption[] }
  | { kind: 'error'; message: string }

// Search box -> Google candidates -> the user taps one. Never picks on its own (invariant 8).
// It may sit inside another <form> (Landing), so it has no <form> of its own: Enter is handled here.
export function PlaceSearch({ inputId, city, placeholder, picked, onPick }: Props) {
  const [query, setQuery] = useState('')
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })
  const [editing, setEditing] = useState(picked === null)

  async function run() {
    if (query.trim() === '') return
    setPhase({ kind: 'searching' })
    try {
      const { candidates } = await searchPlaces(query.trim(), city.trim() || undefined)
      setPhase({ kind: 'results', options: candidates })
    } catch (e) {
      const message = e instanceof ApiError && e.status === 503 ? '장소 검색이 아직 설정되지 않았어요' : '검색하지 못했어요. 다시 해 주세요'
      setPhase({ kind: 'error', message })
    }
  }

  if (picked && !editing) {
    return (
      <div className="place-search__picked">
        <span>
          <b>{picked.name}</b>
          {picked.address && <span>{picked.address}</span>}
        </span>
        <button type="button" onClick={() => setEditing(true)}>
          바꾸기
        </button>
      </div>
    )
  }

  return (
    <div className="place-search">
      <div className="place-search__row">
        <input
          id={inputId}
          type="search"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault() // don't submit the outer form
              void run()
            }
          }}
        />
        <button type="button" onClick={() => void run()} disabled={query.trim() === '' || phase.kind === 'searching'}>
          찾기
        </button>
      </div>

      {phase.kind === 'searching' && <p className="place-search__msg">찾고 있어요…</p>}
      {phase.kind === 'error' && <p className="place-search__msg place-search__msg--warn">{phase.message}</p>}
      {phase.kind === 'results' && phase.options.length === 0 && (
        <p className="place-search__msg">찾은 곳이 없어요. 다른 이름으로 찾아 주세요</p>
      )}
      {phase.kind === 'results' && phase.options.length > 0 && (
        <ul className="place-search__list">
          {phase.options.map((o) => (
            <li key={o.place_id}>
              <button
                type="button"
                onClick={() => {
                  onPick(o, query.trim())
                  setEditing(false)
                  setPhase({ kind: 'idle' })
                }}
              >
                <b>{o.name}</b>
                {o.address && <span>{o.address}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
