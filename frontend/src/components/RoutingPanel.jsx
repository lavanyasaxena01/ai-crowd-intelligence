import { displayOrNA, riskColor } from '../utils/format'

export default function RoutingPanel({
  zoneOptions,
  routeFrom,
  routeTo,
  onFrom,
  onTo,
  onFind,
  loading,
  routeResult,
}) {
  return (
    <div className="glass-panel">
      <h2>Smart Routing</h2>
      <p className="panel-sub">Find the safest path through the venue graph.</p>
      <div className="field">
        <label htmlFor="from">From</label>
        <select id="from" value={routeFrom} onChange={(e) => onFrom(e.target.value)}>
          {zoneOptions.map((id) => <option key={id} value={id}>{id}</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor="to">To</label>
        <select id="to" value={routeTo} onChange={(e) => onTo(e.target.value)}>
          {zoneOptions.map((id) => <option key={id} value={id}>{id}</option>)}
        </select>
      </div>
      <button type="button" className="run-btn compact" disabled={!!loading || !routeFrom || !routeTo} onClick={onFind}>
        ◉ FIND SAFEST ROUTE
      </button>

      {routeResult?.status === 'no_route' && (
        <div className="empty-state compact warn">
          <strong>NO VIABLE ROUTE</strong>
          <p>No valid path exists between the selected nodes.</p>
        </div>
      )}

      {routeResult?.status === 'ok' && routeResult.recommended && (
        <div className="route-result">
          <div className="section-label">Recommended Route</div>
          <div className="route-path">
            {routeResult.recommended.path.map((hop, i) => (
              <div key={`${hop}-${i}`}>
                {hop}
                {i < routeResult.recommended.path.length - 1 ? ' ↓' : ''}
              </div>
            ))}
          </div>
          <div className="kv"><span>Distance</span><span>{displayOrNA(routeResult.recommended.distance_m, (v) => `${v} m`)}</span></div>
          <div className="kv"><span>Travel Time</span><span>{displayOrNA(routeResult.recommended.travel_time_s, (v) => `${v} sec`)}</span></div>
          <div className="kv">
            <span>Risk</span>
            <span style={{ color: riskColor(routeResult.recommended.risk_level) }}>
              {routeResult.recommended.risk_score} {routeResult.recommended.risk_level}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
