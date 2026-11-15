import { Outlet } from 'react-router'

// Screens that draw their own top area (e.g. the Landing hero): frame only, no header, no tab bar.
export default function BareLayout() {
  return (
    <main className="app-frame__main">
      <Outlet />
    </main>
  )
}
