import { apiRequest } from './client'

export function recommendIntervention() {
  return apiRequest('/api/intervention/recommend')
}

export function simulateIntervention(payload = {}) {
  return apiRequest('/api/intervention/simulate', {
    method: 'POST',
    body: payload,
    timeoutMs: 120000,
  })
}
