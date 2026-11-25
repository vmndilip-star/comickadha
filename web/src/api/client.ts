import type { ErrorBody } from '@/types'

/** Every API error carries a kid-friendly message that can be shown as-is. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  /** The input the message is about (e.g. "synopsis"), to show it under that field. */
  readonly field: string | null

  constructor(status: number, code: string, message: string, field: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.field = field
  }
}

const FALLBACK_MESSAGE = 'Oops! Something went wrong. Please try again.'
const NETWORK_MESSAGE = "We can't reach Comickadha right now. Check your internet and try again."

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

function isErrorBody(value: unknown): value is ErrorBody {
  return typeof value === 'object' && value !== null && 'code' in value && 'message' in value
}

export async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      // Lets autosaves finish even if the kid closes or refreshes the page.
      keepalive: method !== 'GET',
    })
  } catch {
    throw new ApiError(0, 'network', NETWORK_MESSAGE)
  }
  if (res.status === 204) return undefined as T

  const data: unknown = await res.json().catch(() => null)
  if (!res.ok) {
    if (isErrorBody(data)) throw new ApiError(res.status, data.code, data.message, data.field ?? null)
    throw new ApiError(res.status, 'server_error', FALLBACK_MESSAGE)
  }
  return data as T
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : FALLBACK_MESSAGE
}
