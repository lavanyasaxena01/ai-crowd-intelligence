import { useEffect, useMemo, useState } from 'react'
import CommandHeader from '../components/CommandHeader'
import SimulationControls from '../components/SimulationControls'
import KPIStrip from '../components/KPIStrip'
import RiskHUD from '../components/RiskHUD'
import VenueDigitalTwin from '../components/VenueDigitalTwin'
import BottleneckAlert from '../components/BottleneckAlert'
import ForecastChart from '../components/ForecastChart'
import ZoneTelemetry from '../components/ZoneTelemetry'
import ZoneInspector from '../components/ZoneInspector'
import RoutingPanel from '../components/RoutingPanel'
import InterventionPanel from '../components/InterventionPanel'
import WhatIfPanel from '../components/WhatIfPanel'
import VisionIntelligence from '../components/VisionIntelligence'
import { useSystemBootstrap, useVenueGraph } from '../hooks/useSystem'
import { useSimulationActions } from '../hooks/useSimulationActions'

const DEFAULT_DURATION = 600

export default function CommandCenter() {
  const {
    online,
    venues,
    scenarios,
    loading: bootLoading,
    error: bootError,
    setError: setBootError,
    refresh,
    modelLoaded,
    simulatorReady,
  } = useSystemBootstrap()

  const [venue, setVenue] = useState('')
  const [scenario, setScenario] = useState('peak_traffic')
  const [duration, setDuration] = useState(DEFAULT_DURATION)
  const [arrivalRate, setArrivalRate] = useState('')
  const [expectedCrowd, setExpectedCrowd] = useState(30000)
  const [eventStart, setEventStart] = useState('18:00')
  const [peakWindow, setPeakWindow] = useState(30)
  const [eventDuration, setEventDuration] = useState(120)
  const [selectedZone, setSelectedZone] = useState(null)
  const [routeFrom, setRouteFrom] = useState('')
  const [routeTo, setRouteTo] = useState('')
  const [whatIfRate, setWhatIfRate] = useState(24)

  const { graph, setGraph } = useVenueGraph(venue, online)
  const {
    sim,
    routeResult,
    intervention,
    interventionResult,
    whatIfResult,
    loading: actionLoading,
    error: actionError,
    setError: setActionError,
    lastUpdated,
    run,
    route,
    applyIntervention,
    whatIf,
  } = useSimulationActions({
    venue,
    scenario,
    duration,
    arrivalRate,
    expectedCrowd,
    eventStart,
    peakWindow,
    eventDuration,
    onGraph: setGraph,
  })

  useEffect(() => {
    if (!venues.length) return
    setVenue((prev) => prev || venues.find((v) => v.id === 'stadium')?.id || venues[0].id)
  }, [venues])

  useEffect(() => {
    if (!scenarios.length) return
    setScenario((prev) => {
      if (prev && scenarios.some((s) => s.id === prev)) return prev
      return scenarios.find((s) => s.id === 'peak_traffic')?.id || scenarios[0].id
    })
  }, [scenarios])

  useEffect(() => {
    if (!graph) return
    const gates = graph.gates || []
    const exits = graph.exits || []
    const eventZones = graph.event_zones || []
    setRouteFrom(gates[0] || graph.nodes?.[0]?.id || '')
    setRouteTo(eventZones[0] || exits[0] || graph.nodes?.[1]?.id || '')
  }, [graph])

  // Dynamic rerouting: when crowd state updates, refresh recommended route.
  useEffect(() => {
    if (!sim || !routeFrom || !routeTo || !venue) return undefined
    let cancelled = false
    ;(async () => {
      try {
        await route(routeFrom, routeTo)
      } catch {
        if (!cancelled) {
          /* route errors already surfaced via hook */
        }
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sim?.updated_at, routeFrom, routeTo, venue])

  const loading = bootLoading || actionLoading
  const error = actionError || bootError
  const zones = sim?.zones || []
  const zoneOptions = useMemo(() => (graph?.nodes || []).map((n) => n.id), [graph])
  const selectedZoneData = zones.find((z) => z.zone === selectedZone) || null

  async function handleRun() {
    setBootError('')
    setActionError('')
    try {
      const result = await run()
      setSelectedZone(result?.bottleneck?.zone || result?.zones?.[0]?.zone || null)
    } catch (err) {
      if (/Unable to connect/i.test(err.message)) refresh()
    }
  }

  async function handleIntervention() {
    const result = await applyIntervention()
    if (result?.status === 'applied' && routeFrom && routeTo) {
      try {
        await route(routeFrom, routeTo)
      } catch {
        /* ignore */
      }
    }
  }

  if (!online && !loading) {
    return (
      <div className="cc-shell">
        <CommandHeader online={false} modelLoaded={false} simulatorReady={false} onRefresh={refresh} />
        <div className="offline-hero" role="alert">
          <h2>BACKEND OFFLINE</h2>
          <p>Unable to connect to Crowd Intelligence API. Please start the backend server and try again.</p>
          <button type="button" className="run-btn" onClick={refresh}>RETRY CONNECTION</button>
        </div>
      </div>
    )
  }

  return (
    <div className="cc-shell">
      <CommandHeader
        online={online}
        modelLoaded={modelLoaded}
        simulatorReady={simulatorReady}
        onRefresh={refresh}
      />

      {loading && <div className="loading-ribbon" role="status">{loading}</div>}
      {error && <div className="error-banner" role="alert"><strong>Error:</strong> {error}</div>}

      <SimulationControls
        venues={venues}
        scenarios={scenarios}
        venue={venue}
        scenario={scenario}
        duration={duration}
        arrivalRate={arrivalRate}
        expectedCrowd={expectedCrowd}
        eventStart={eventStart}
        peakWindow={peakWindow}
        eventDuration={eventDuration}
        loading={loading}
        lastUpdated={lastUpdated || sim?.updated_at}
        onVenue={setVenue}
        onScenario={setScenario}
        onDuration={setDuration}
        onArrival={setArrivalRate}
        onExpectedCrowd={setExpectedCrowd}
        onEventStart={setEventStart}
        onPeakWindow={setPeakWindow}
        onEventDuration={setEventDuration}
        onRun={handleRun}
      />

      <KPIStrip stats={sim?.stats} totalPeople={sim?.total_people} />

      <section className="hero-grid">
        <RiskHUD
          stats={sim?.stats}
          highRiskZones={sim?.high_risk_zones}
          onSelectZone={setSelectedZone}
        />
        <VenueDigitalTwin
          graph={graph}
          zones={zones}
          selectedZoneId={selectedZone}
          onSelectZone={setSelectedZone}
          routePath={routeResult?.status === 'ok' ? routeResult?.recommended?.path : null}
        />
        <ZoneInspector
          zone={selectedZoneData}
          onFindRoute={selectedZone ? () => setRouteFrom(selectedZone) : undefined}
        />
      </section>

      <BottleneckAlert bottleneck={sim?.bottleneck} />

      <section className="mid-grid">
        <div className="glass-panel">
          <h2>Predictive Crowd Forecast</h2>
          <p className="panel-sub">Current density vs predicted condition from backend model</p>
          {sim?.forecast?.length ? (
            <ForecastChart forecast={sim.forecast} />
          ) : (
            <div className="empty-state compact">
              <div className="empty-icon">◌</div>
              <strong>NO FORECAST AVAILABLE</strong>
              <p>Run a simulation to generate predictive crowd data.</p>
            </div>
          )}
        </div>
        <ZoneTelemetry zones={zones} selectedZoneId={selectedZone} onSelectZone={setSelectedZone} />
      </section>

      <section className="bottom-grid">
        <RoutingPanel
          zoneOptions={zoneOptions}
          routeFrom={routeFrom}
          routeTo={routeTo}
          onFrom={setRouteFrom}
          onTo={setRouteTo}
          onFind={() => route(routeFrom, routeTo)}
          loading={loading}
          routeResult={routeResult}
        />
        <InterventionPanel
          intervention={intervention}
          interventionResult={interventionResult}
          loading={loading}
          onSimulate={handleIntervention}
        />
        <WhatIfPanel
          currentArrival={sim?.arrival_rate}
          whatIfRate={whatIfRate}
          onRate={setWhatIfRate}
          onRun={() => whatIf(whatIfRate)}
          loading={loading}
          disabled={!sim}
          whatIfResult={whatIfResult}
        />
      </section>

      <VisionIntelligence online={online} />

      <footer className="cc-footer">
        Crowd Flow Optimiser · Simulation Mode · Hugging Face Hub vision (optional camera stills) · No fake production values
      </footer>
    </div>
  )
}
