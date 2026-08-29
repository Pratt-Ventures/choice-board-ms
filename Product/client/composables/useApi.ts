export class ApiError extends Error {
  status: number
  data: unknown

  constructor(message: string, status: number, data?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

function resolveBaseUrl(): string {
  const config = useRuntimeConfig()
  // In browser during Nuxt dev, prefer same-origin so Vite proxy handles cookies.
  if (import.meta.client && import.meta.dev) {
    return ''
  }
  return (config.public.apiBase as string) || ''
}

export function useApi() {
  async function apiFetch<T>(
    path: string,
    options: {
      method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
      body?: unknown
      query?: Record<string, string | number | boolean | undefined | null>
    } = {},
  ): Promise<T> {
    const base = resolveBaseUrl()
    const method = options.method || 'GET'
    const url = new URL(path.startsWith('http') ? path : `${base}${path}`, import.meta.client ? window.location.origin : 'http://localhost:3000')

    if (options.query) {
      for (const [key, value] of Object.entries(options.query)) {
        if (value !== undefined && value !== null && value !== '') {
          url.searchParams.set(key, String(value))
        }
      }
    }

    const headers: Record<string, string> = {
      Accept: 'application/json',
    }

    let body: string | undefined
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json'
      body = JSON.stringify(options.body)
    }

    const response = await fetch(url.toString(), {
      method,
      headers,
      body,
      credentials: 'include',
    })

    const contentType = response.headers.get('content-type') || ''
    const isJson = contentType.includes('application/json')
    const data = isJson ? await response.json().catch(() => null) : await response.text()

    if (!response.ok) {
      let message = `Request failed (${response.status})`
      if (data && typeof data === 'object') {
        const detail = (data as { detail?: unknown; failure_reason?: string }).detail
        const failure = (data as { failure_reason?: string }).failure_reason
        if (typeof detail === 'string') message = detail
        else if (Array.isArray(detail)) message = detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(', ')
        else if (failure) message = failure
      }
      else if (typeof data === 'string' && data) {
        message = data
      }
      throw new ApiError(message, response.status, data)
    }

    return data as T
  }

  return { apiFetch }
}
