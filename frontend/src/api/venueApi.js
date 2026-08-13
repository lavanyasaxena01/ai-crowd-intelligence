import { apiRequest } from './client'

export function fetchHealth() {
  return apiRequest('/api/health', { timeoutMs: 8000 })
}

export function fetchVenues() {
  return apiRequest('/api/venues')
}

export function fetchScenarios() {
  return apiRequest('/api/scenarios')
}

export function fetchVenueGraph(venueId) {
  return apiRequest(`/api/venues/${encodeURIComponent(venueId)}/graph`)
}
