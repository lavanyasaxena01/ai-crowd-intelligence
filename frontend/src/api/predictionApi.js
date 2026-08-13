import { apiRequest } from './client'

export function runWhatIf(payload) {
  return apiRequest('/api/what-if', {
    method: 'POST',
    body: payload,
    timeoutMs: 120000,
  })
}
