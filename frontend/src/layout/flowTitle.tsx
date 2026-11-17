// Lets a screen inside FlowLayout put its name in the top bar ("패치 고르기 · 후보 2개").
import { createContext, useContext, useEffect } from 'react'

export type FlowTitle = { title?: string; aside?: string }

export const FlowTitleContext = createContext<(t: FlowTitle) => void>(() => {})

/** Show `title` (and a short `aside` on the right) in the flow top bar while this screen is open. */
export function useFlowTitle(title: string, aside?: string) {
  const set = useContext(FlowTitleContext)
  useEffect(() => {
    set({ title, aside })
    return () => set({})
  }, [set, title, aside])
}
