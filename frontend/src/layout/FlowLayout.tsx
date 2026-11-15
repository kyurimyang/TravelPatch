import { Outlet } from 'react-router'
import TopBar from './TopBar'

// Screens inside a flow (register, recover...): back-button header, no tab bar.
export default function FlowLayout() {
  return (
    <>
      <TopBar variant="flow" />
      <main className="app-frame__main">
        <Outlet />
      </main>
    </>
  )
}
