// Backend problems the UI should tell apart from a network failure.
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** No answer in time: the server or the network is stuck. The UI shows its "try again" message
 * instead of a loader that never ends (review 2026-11-19, A7). */
export class RequestTimeoutError extends Error {
  constructor(path: string, ms: number) {
    super(`${path}: no answer in ${ms} ms`)
    this.name = 'RequestTimeoutError'
  }
}

/** Most calls answer in a few seconds (places, plan build, engine). */
export const DEFAULT_TIMEOUT_MS = 20_000
/** Calls that wait on the LLM, which the server may ask twice (invariant 4). Draft values. */
export const LLM_TIMEOUT_MS = 60_000

export type RequestOptions = { timeoutMs?: number }

async function fetchWithTimeout(path: string, init: RequestInit, ms: number): Promise<Response> {
  const ctrl = new AbortController()
  // Our own timer, not AbortSignal.timeout(): it is cleared as soon as the answer is in.
  const timer = setTimeout(() => ctrl.abort(new RequestTimeoutError(path, ms)), ms)
  try {
    return await fetch(`/api${path}`, { ...init, signal: ctrl.signal })
  } catch (e) {
    throw ctrl.signal.aborted ? ctrl.signal.reason : e
  } finally {
    clearTimeout(timer)
  }
}

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    // FastAPI puts the reason in `detail` (a string for 501/502/503, a list for 422).
    const err = (await res.json().catch(() => null)) as { detail?: unknown } | null
    const detail = typeof err?.detail === 'string' ? err.detail : res.statusText
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

export async function postJson<T>(path: string, body: unknown, opts: RequestOptions = {}): Promise<T> {
  const init = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
  return readJson<T>(await fetchWithTimeout(path, init, opts.timeoutMs ?? DEFAULT_TIMEOUT_MS))
}

export async function getJson<T>(
  path: string,
  params: Record<string, string | undefined>,
  opts: RequestOptions = {},
): Promise<T> {
  const query = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') query.set(k, v)
  return readJson<T>(await fetchWithTimeout(`${path}?${query}`, {}, opts.timeoutMs ?? DEFAULT_TIMEOUT_MS))
}
