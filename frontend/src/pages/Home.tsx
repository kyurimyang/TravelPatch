import TabLayout from '../layout/TabLayout'
import { useAuth } from '../store/auth'
import { useTrip } from '../store/trip'
import Intro from './Intro'
import Main from './Main'

// "/": the intro while there is no trip yet, today's fabric (Main) once there is one.
// Until the session and the account are read we cannot tell which: show the Main frame with
// placeholder blocks, so a signed-in user sees neither the intro nor "no trip yet" flash by.
export default function Home() {
  const { ready } = useAuth()
  const { trip, sync } = useTrip()
  const deciding = !trip && (!ready || sync.kind === 'loading')
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
  if (!trip) {
    return (
      <main className="app-frame__main">
        <Intro />
      </main>
    )
  }
  return (
    <TabLayout>
      <Main />
    </TabLayout>
  )
}
