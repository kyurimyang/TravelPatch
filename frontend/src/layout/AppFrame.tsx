import { Outlet } from 'react-router'
import './AppFrame.css'

// Layout route: renders the shared phone-width frame, and <Outlet /> is where the
// matched child route (a page) is drawn.
export default function AppFrame() {
  return (
    <div className="app-frame">
      <div className="app-frame__column tp-linen-tex">
        <Outlet />
      </div>
    </div>
  )
}
