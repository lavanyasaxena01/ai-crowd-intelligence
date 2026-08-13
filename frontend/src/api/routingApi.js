import { apiRequest } from './client'

export function findSafestRoute(payload) {
  return apiRequest('/api/routing', {
    method: 'POST',
    body: payload,
    timeoutMs: 30000,
  })
}
