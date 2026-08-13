import { apiRequest } from './client'

export function fetchVisionStatus() {
  return apiRequest('/api/vision/status', { timeoutMs: 8000 })
}

export async function analyzeVisionImage(file) {
  const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
  const form = new FormData()
  form.append('file', file)

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 120000)
  try {
    const response = await fetch(`${BASE_URL}/api/vision/analyze`, {
      method: 'POST',
      body: form,
      signal: controller.signal,
    })
    const text = await response.text()
    let payload = null
    if (text) {
      try {
        payload = JSON.parse(text)
      } catch {
        payload = { detail: text }
      }
    }
    if (!response.ok) {
      const detail = payload?.detail || response.statusText || 'Vision analysis failed'
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    }
    return payload
  } finally {
    clearTimeout(timer)
  }
}
