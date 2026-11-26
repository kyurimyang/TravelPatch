import { Route, Routes } from 'react-router'
import AppFrame from './layout/AppFrame'
import Admin from './pages/Admin'
import BareLayout from './layout/BareLayout'
import FlowLayout from './layout/FlowLayout'
import TabLayout from './layout/TabLayout'
import Confirm from './pages/Confirm'
import Consent from './pages/Consent'
import DiffView from './pages/DiffView'
import Grade from './pages/Grade'
import Guide from './pages/Guide'
import Home from './pages/Home'
import Landing from './pages/Landing'
import Legal from './pages/Legal'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import NoPatch from './pages/NoPatch'
import Patchwork from './pages/Patchwork'
import Recover from './pages/Recover'
import Settings from './pages/Settings'
import Signup from './pages/Signup'
import Stitched from './pages/Stitched'
import TripList from './pages/TripList'
import Withdraw from './pages/Withdraw'

export default function AppRoutes() {
  return (
    <Routes>
      {/* Pathless layout routes: they add no URL segment, they only wrap their children. */}
      <Route element={<AppFrame />}>
        {/* Intro with no trip, Main with one: Home picks its own frame. */}
        <Route index element={<Home />} />
        <Route element={<TabLayout />}>
          <Route path="trips" element={<TripList />} />
          <Route path="patchwork" element={<Patchwork />} />
        </Route>
        <Route element={<BareLayout />}>
          <Route path="recover/done" element={<Stitched />} />
        </Route>
        <Route element={<FlowLayout />}>
          <Route path="new" element={<Landing />} />
          <Route path="new/confirm" element={<Confirm />} />
          <Route path="new/grade" element={<Grade />} />
          <Route path="trips/:id/edit" element={<Confirm />} />
          <Route path="trips/:id/grade" element={<Grade />} />
          <Route path="recover" element={<Recover />} />
          <Route path="recover/patch" element={<DiffView />} />
          <Route path="recover/blocked" element={<NoPatch />} />
          <Route path="login" element={<Login />} />
          <Route path="signup" element={<Signup />} />
          <Route path="consent" element={<Consent />} />
          <Route path="legal/:doc" element={<Legal />} />
          <Route path="guide" element={<Guide />} />
          <Route path="settings" element={<Settings />} />
          <Route path="settings/withdraw" element={<Withdraw />} />
          <Route path="admin" element={<Admin />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  )
}
