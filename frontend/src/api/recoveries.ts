import type { RecoveryInput, RecoveryResponse } from './types'

// Backend problems the UI should tell apart from a network failure.
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function createRecovery(input: RecoveryInput): Promise<RecoveryResponse> {
  const res = await fetch('/api/recoveries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  if (!res.ok) {
    // FastAPI puts the reason in `detail` (a string for 501, a list for 422).
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null
    const detail = typeof body?.detail === 'string' ? body.detail : res.statusText
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as RecoveryResponse
}
