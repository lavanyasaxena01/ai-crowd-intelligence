import { useCallback, useState } from 'react'
import { runSimulation } from '../api/simulationApi'
import { findSafestRoute } from '../api/routingApi'
import { recommendIntervention, simulateIntervention } from '../api/interventionApi'
import { runWhatIf } from '../api/predictionApi'

export function useSimulationActions({
  venue,
  scenario,
  duration,
  arrivalRate,
  expectedCrowd,
  eventStart,
  peakWindow,
  eventDuration,
  onGraph,
}) {
  const [sim, setSim] = useState(null)
  const [routeResult, setRouteResult] = useState(null)
  const [intervention, setIntervention] = useState(null)
  const [interventionResult, setInterventionResult] = useState(null)
  const [whatIfResult, setWhatIfResult] = useState(null)
  const [loading, setLoading] = useState('')
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)

  const clearDerived = useCallback(() => {
    setRouteResult(null)
    setIntervention(null)
    setInterventionResult(null)
    setWhatIfResult(null)
  }, [])

  const run = useCallback(async () => {
    setError('')
    clearDerived()
    setLoading('Running simulation...')
    try {
      const payload = {
        venue,
        scenario,
        duration_seconds: Number(duration),
        random_seed: 42,
        expected_crowd_size: expectedCrowd === '' || expectedCrowd == null ? null : Number(expectedCrowd),
        event_schedule: {
          start_time: eventStart || null,
          peak_window_minutes: Number(peakWindow) || 30,
          event_duration_minutes: Number(eventDuration) || 120,
        },
      }
      if (arrivalRate !== '' && arrivalRate != null && !Number.isNaN(Number(arrivalRate))) {
        payload.arrival_rate = Number(arrivalRate)
      }
      const result = await runSimulation(payload)
      setSim(result)
      onGraph?.(result.graph)
      setLastUpdated(result.updated_at || new Date().toISOString())
      setLoading('Calculating risk / predicting bottlenecks...')
      try {
        const rec = await recommendIntervention()
        setIntervention(rec)
      } catch {
        setIntervention(null)
      }
      return result
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading('')
    }
  }, [
    venue,
    scenario,
    duration,
    arrivalRate,
    expectedCrowd,
    eventStart,
    peakWindow,
    eventDuration,
    clearDerived,
    onGraph,
  ])

  const route = useCallback(async (source, target) => {
    setError('')
    setLoading('Finding safest route...')
    try {
      const result = await findSafestRoute({
        venue,
        source,
        target,
        max_alternates: 3,
      })
      setRouteResult(result)
      return result
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading('')
    }
  }, [venue])

  const applyIntervention = useCallback(async () => {
    setError('')
    setLoading('Evaluating intervention...')
    try {
      const result = await simulateIntervention({
        redirect_percentage: intervention?.recommended_action?.redirect_percentage
          ?? intervention?.recommended_action?.percentage
          ?? undefined,
      })
      setInterventionResult(result)
      if (result.status === 'applied' && result.after) {
        setSim((prev) => ({
          ...prev,
          stats: result.after.stats,
          zones: result.after.zones,
          bottleneck: result.after.bottleneck,
          forecast: result.after.forecast,
          predictions: result.after.predictions,
          high_risk_zones: result.after.high_risk_zones,
          graph: result.after.graph || prev?.graph,
          total_people: result.after.total_crowd ?? result.after.stats?.total_crowd,
        }))
        onGraph?.(result.after.graph)
        setLastUpdated(new Date().toISOString())
        try {
          const rec = await recommendIntervention()
          setIntervention(rec)
        } catch {
          /* keep prior recommendation */
        }
      }
      return result
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading('')
    }
  }, [intervention, onGraph])

  const whatIf = useCallback(async (testArrivalRate) => {
    setError('')
    setLoading('Running what-if simulation...')
    try {
      const result = await runWhatIf({ test_arrival_rate: Number(testArrivalRate) })
      setWhatIfResult(result)
      return result
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading('')
    }
  }, [])

  return {
    sim,
    setSim,
    routeResult,
    setRouteResult,
    intervention,
    interventionResult,
    whatIfResult,
    loading,
    error,
    setError,
    lastUpdated,
    run,
    route,
    applyIntervention,
    whatIf,
    clearDerived,
  }
}
