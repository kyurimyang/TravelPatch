import { Outlet } from 'react-router'
import TabBar from './TabBar'
import TopBar from './TopBar'

// Top-level screens: logo header + bottom tab bar.
export default function TabLayout() {
  return (
    <>
      <TopBar variant="tab" />
      <main className="app-frame__main">
        <Outlet />
      </main>
      <TabBar />
    </>
  )
}
