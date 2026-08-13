const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

const DEFAULT_TIMEOUT_MS = 60000

export class ApiError extends Error {
  constructor(message, { status, detail } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export async function apiRequest(path, { method = 'GET', body, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })

    let payload = null
    const text = await response.text()
    if (text) {
      try {
        payload = JSON.parse(text)
      } catch {
        payload = { detail: text }
      }
    }

    if (!response.ok) {
      const detail = payload?.detail || response.statusText || 'Request failed'
      throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), {
        status: response.status,
        detail,
      })
    }

    return payload
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new ApiError('Request timed out. The backend may still be processing.')
    }
    if (err instanceof ApiError) throw err
    throw new ApiError('Unable to connect to Crowd Intelligence API. Please start the backend server.')
  } finally {
    clearTimeout(timer)
  }
}

export function getApiBaseUrl() {
  return BASE_URL
}
