const DEFAULT_BASE_URL = 'http://localhost:8000'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string }
    if (payload?.detail) {
      return payload.detail
    }
  } catch {
    // keep default message
  }
  return `${response.status} ${response.statusText}`
}

export async function apiRequest<TResponse>(
  path: string,
  init?: RequestInit,
): Promise<TResponse> {
  const isFormData = init?.body instanceof FormData
  const headers = new Headers(init?.headers)
  if (!isFormData) {
    headers.set('Content-Type', 'application/json')
  }

  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    throw new ApiError(await parseErrorMessage(response), response.status)
  }

  if (response.status === 204) {
    return undefined as TResponse
  }

  return (await response.json()) as TResponse
}
