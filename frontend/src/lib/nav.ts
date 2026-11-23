// Where to go back to. A flow (register a trip, recover a day) is a run of screens opened from
// one screen; leaving it should return there and pop the flow's screens, so "back" afterwards
// does not walk through finished steps again. Entered directly (shared link, new tab), there is
// nothing to pop: go home instead of leaving the app.
import type { NavigateFunction } from 'react-router'

export type Flow = 'new' | 'recover'

const FLOW_KEY = (flow: Flow) => `tp.flow.${flow}`
const NEXT_KEY = 'tp.next'

/** Position of the current entry in this tab's history. react-router's BrowserRouter keeps it
 *  in history.state.idx; 0 = the first screen opened in this tab. */
export function historyIdx(): number {
  const s = window.history.state as { idx?: unknown } | null
  return typeof s?.idx === 'number' ? s.idx : 0
}

function read(key: string): string | null {
  try {
    return sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) sessionStorage.removeItem(key)
    else sessionStorage.setItem(key, value)
  } catch {
    // Storage blocked (private mode): flows fall back to going home.
  }
}

/** Call on the first screen of a flow: remembers where in history the flow started. */
export function markFlowStart(flow: Flow) {
  write(FLOW_KEY(flow), String(historyIdx()))
}

function flowStart(flow: Flow): number | null {
  const n = Number(read(FLOW_KEY(flow)))
  return Number.isInteger(n) && read(FLOW_KEY(flow)) !== null ? n : null
}

/** Leave the flow: back to the screen it was opened from, or home (replacing) if there is none. */
export function exitFlow(navigate: NavigateFunction, flow: Flow) {
  const start = flowStart(flow)
  const delta = start === null ? 0 : start - 1 - historyIdx()
  if (start !== null && start > 0 && delta < 0) navigate(delta)
  else navigate('/', { replace: true })
}

/** Back to the flow's first screen (e.g. "enter the situation again"), popping the steps after it. */
export function backToFlowStart(navigate: NavigateFunction, flow: Flow, path: string) {
  const start = flowStart(flow)
  const delta = start === null ? 0 : start - historyIdx()
  if (start !== null && delta < 0) navigate(delta)
  else navigate(path, { replace: true })
}

/** The top bar's back button: one step back, or home when this tab opened on this screen. */
export function goBack(navigate: NavigateFunction) {
  if (historyIdx() > 0) navigate(-1)
  else navigate('/', { replace: true })
}

/** Only paths inside this app: "/x", never "//host" or "https://...". Anything else = home. */
export function safeNext(raw: string | null | undefined): string {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//') || raw.startsWith('/\\')) return '/'
  if (raw.startsWith('/login') || raw.startsWith('/signup')) return '/'
  return raw
}

/** Login URL that returns to `path` afterwards. */
export function loginPath(path: string, to: '/login' | '/signup' = '/login'): string {
  const next = safeNext(path)
  return next === '/' ? to : `${to}?next=${encodeURIComponent(next)}`
}

/** Google sign-in leaves the site and comes back to "/": keep the destination for the return. */
export function holdNext(next: string) {
  write(NEXT_KEY, next === '/' ? null : next)
}

/** The destination held before Google sign-in, read once. */
export function takeHeldNext(): string | null {
  const v = read(NEXT_KEY)
  write(NEXT_KEY, null)
  return v ? safeNext(v) : null
}
