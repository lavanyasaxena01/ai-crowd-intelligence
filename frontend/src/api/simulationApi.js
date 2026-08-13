import { apiRequest } from './client'

export function runSimulation(payload) {
  return apiRequest('/api/simulation', {
    method: 'POST',
    body: payload,
    timeoutMs: 120000,
  })
}
