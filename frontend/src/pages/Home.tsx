import TabLayout from '../layout/TabLayout'
import { useTrip } from '../store/trip'
import Intro from './Intro'
import Main from './Main'

// "/": the intro while there is no trip yet, today's fabric (Main) once there is one.
// While the account is still being read, keep the Main frame so a signed-in user
// does not see the intro flash by.
export default function Home() {
  const { trip, sync } = useTrip()
  if (!trip && sync.kind !== 'loading') {
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
