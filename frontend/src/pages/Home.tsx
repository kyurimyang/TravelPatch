import { useEffect } from 'react'
import TabBar from '../layout/TabBar'
import TabLayout from '../layout/TabLayout'
import { deviceNow, pickTrip } from '../lib/today'
import { useAuth } from '../store/auth'
import { useTrip } from '../store/trip'
import Intro from './Intro'
import Main from './Main'

// "/" (decision 2026-11-23): someone who has trips never lands on the intro.
// - a trip is chosen: today's fabric (Main);
// - none chosen but there are trips (a new device, the chosen one deleted): open the one being
//   travelled, else the next one, else the last one (lib/today pickTrip);
// - signed in with no trip at all: Main's empty state ("first trip"), with the tab bar;
// - a guest with no trip: the intro, now with the tab bar too, so it is never a dead end.
// Until the session and the account are read we cannot tell which: the Main frame with
// placeholder blocks, so a signed-in user sees neither the intro nor "no trip yet" flash by.
export default function Home() {
  const { ready, user } = useAuth()
  const { trip, trips, sync, selectTrip } = useTrip()
  const pick = trip ? null : pickTrip(trips, deviceNow().date)
  const pickId = pick?.id ?? null
  // Once per picked id: selectTrip is a new function every render.
  useEffect(() => {
    if (pickId) selectTrip(pickId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickId])

  const deciding = !trip && (!ready || sync.kind === 'loading' || pick !== null)
  if (deciding) {
    return (
      <TabLayout>
        <div className="main-screen" aria-busy="true" aria-label="여행을 불러오고 있어요">
          <div className="main-screen__skeleton main-screen__skeleton--title" />
          <div className="main-screen__skeleton main-screen__skeleton--map" />
          <div className="main-screen__skeleton main-screen__skeleton--row" />
          <div className="main-screen__skeleton main-screen__skeleton--row" />
        </div>
      </TabLayout>
    )
  }
  if (!trip && !user) {
    return (
      <>
        <main className="app-frame__main">
          <Intro />
        </main>
        <TabBar />
      </>
    )
  }
  return (
    <TabLayout>
      <Main />
    </TabLayout>
  )
}
