export default function SimulationControls({
  venues,
  scenarios,
  venue,
  scenario,
  duration,
  arrivalRate,
  expectedCrowd,
  eventStart,
  peakWindow,
  eventDuration,
  loading,
  onVenue,
  onScenario,
  onDuration,
  onArrival,
  onExpectedCrowd,
  onEventStart,
  onPeakWindow,
  onEventDuration,
  onRun,
  lastUpdated,
}) {
  return (
    <section className="control-console extended" aria-label="Simulation controls">
      <div className="field">
        <label htmlFor="venue">Venue</label>
        <select id="venue" value={venue} onChange={(e) => onVenue(e.target.value)}>
          {venues.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor="scenario">Scenario</label>
        <select id="scenario" value={scenario} onChange={(e) => onScenario(e.target.value)}>
          {scenarios.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor="crowd">Expected Crowd Size</label>
        <input
          id="crowd"
          type="number"
          min={0}
          step={500}
          value={expectedCrowd}
          onChange={(e) => onExpectedCrowd(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="arrival">Arrival Rate (optional)</label>
        <input
          id="arrival"
          type="number"
          min={0}
          step={0.5}
          value={arrivalRate}
          onChange={(e) => onArrival(e.target.value)}
          placeholder="auto from crowd"
        />
      </div>
      <div className="field">
        <label htmlFor="duration">Sim Duration (sec)</label>
        <input id="duration" type="number" min={60} max={3600} step={60} value={duration} onChange={(e) => onDuration(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="start">Event Start</label>
        <input id="start" type="time" value={eventStart} onChange={(e) => onEventStart(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="peak">Peak Window (min)</label>
        <input id="peak" type="number" min={5} max={240} value={peakWindow} onChange={(e) => onPeakWindow(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="edur">Event Duration (min)</label>
        <input id="edur" type="number" min={15} max={600} value={eventDuration} onChange={(e) => onEventDuration(e.target.value)} />
      </div>
      <div className="console-meta">
        <div className="live-chip">{loading ? '● RUNNING' : lastUpdated ? '● SIMULATION MODE' : '○ STANDBY'}</div>
        <button type="button" className="run-btn" disabled={!!loading || !venue || !scenario} onClick={onRun}>
          {loading ? 'SIMULATING…' : '▶ RUN SIMULATION'}
        </button>
      </div>
    </section>
  )
}
