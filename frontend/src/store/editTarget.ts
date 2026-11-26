// "/trips/:id/edit" and "/trips/:id/grade" name their trip in the URL, but the store changes the
// *current* trip. This selects it, and says whether the screen can show it yet.
import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { deviceNow } from '../lib/today'
import { useAuth } from './auth'
import { useTrip } from './trip'

export type EditTarget = {
  /** false on the registration screens (/new/...), which have no id in the URL. */
  editing: boolean
  /** loading: the session or the account is still being read. missing: no such trip. */
  status: 'ready' | 'loading' | 'missing'
  today: string
}

export function useEditTarget(): EditTarget {
  const { id } = useParams()
  const { ready } = useAuth()
  const { trip, trips, sync, selectTrip } = useTrip()
  const [today] = useState(() => deviceNow().date)
  const exists = trips.some((t) => t.id === id)
  const current = trip?.id === id

  useEffect(() => {
    if (id && exists && !current) selectTrip(id)
    // selectTrip is a new function every render (as in Home).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, exists, current])

  if (!id) return { editing: false, status: 'ready', today }
  const waiting = exists || !ready || sync.kind === 'loading'
  return { editing: true, status: current ? 'ready' : waiting ? 'loading' : 'missing', today }
}
