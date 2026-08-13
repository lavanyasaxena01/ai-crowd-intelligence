import { useCallback, useEffect, useState } from 'react'
import { fetchHealth, fetchScenarios, fetchVenueGraph, fetchVenues } from '../api/venueApi'

export function useSystemBootstrap() {
  const [online, setOnline] = useState(false)
  const [health, setHealth] = useState(null)
  const [venues, setVenues] = useState([])
  const [scenarios, setScenarios] = useState([])
  const [loading, setLoading] = useState('')
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setError('')
    setLoading('Connecting to backend...')
    try {
      const h = await fetchHealth()
      setHealth(h)
      setOnline(true)
      const [v, s] = await Promise.all([fetchVenues(), fetchScenarios()])
      setVenues(v.venues || [])
      setScenarios(s.scenarios || [])
      return { health: h, venues: v.venues || [], scenarios: s.scenarios || [] }
    } catch (err) {
      setOnline(false)
      setHealth(null)
      setError(err.message || 'Backend offline')
      return null
    } finally {
      setLoading('')
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return {
    online,
    health,
    venues,
    scenarios,
    loading,
    error,
    setError,
    refresh,
    modelLoaded: Boolean(health?.model_loaded || health?.model_available),
    simulatorReady: Boolean(health?.simulator_ready ?? online),
  }
}

export function useVenueGraph(venue, online) {
  const [graph, setGraph] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!venue || !online) return undefined
    let cancelled = false
    ;(async () => {
      try {
        const data = await fetchVenueGraph(venue)
        if (!cancelled) {
          setGraph(data.graph)
          setError('')
        }
      } catch (err) {
        if (!cancelled) setError(err.message)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [venue, online])

  return { graph, setGraph, error }
}
