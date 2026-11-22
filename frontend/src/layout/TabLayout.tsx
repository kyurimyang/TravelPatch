import type { ReactNode } from 'react'
import { Outlet } from 'react-router'
import TabBar from './TabBar'
import TopBar from './TopBar'

// Top-level screens: logo header + bottom tab bar.
// Used as a layout route (draws <Outlet />) or as a wrapper around `children` (Home).
export default function TabLayout({ children }: { children?: ReactNode }) {
  return (
    <>
      <TopBar variant="tab" />
      <main className="app-frame__main">{children ?? <Outlet />}</main>
      <TabBar />
    </>
  )
}
