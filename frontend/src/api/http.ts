// Backend problems the UI should tell apart from a network failure.
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
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

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return readJson<T>(res)
}

export async function getJson<T>(path: string, params: Record<string, string | undefined>): Promise<T> {
  const query = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') query.set(k, v)
  return readJson<T>(await fetch(`/api${path}?${query}`))
}
