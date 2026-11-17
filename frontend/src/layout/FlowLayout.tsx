import { useState } from 'react'
import { Outlet } from 'react-router'
import { FlowTitleContext, type FlowTitle } from './flowTitle'
import TopBar from './TopBar'

// Screens inside a flow (register, recover...): back-button header, no tab bar.
// A screen may name itself in the header with useFlowTitle().
export default function FlowLayout() {
  const [head, setHead] = useState<FlowTitle>({})
  return (
    <FlowTitleContext.Provider value={setHead}>
      <TopBar variant="flow" title={head.title} aside={head.aside} />
      <main className="app-frame__main">
        <Outlet />
      </main>
    </FlowTitleContext.Provider>
  )
}
