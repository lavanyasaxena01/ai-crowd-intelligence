import { displayOrNA, formatNumber, formatPct, riskColor } from '../utils/format'

export default function ZoneInspector({ zone, onFindRoute }) {
  if (!zone) {
    return (
      <aside className="glass-panel">
        <h2>Zone Inspector</h2>
        <div className="empty-state compact">
          <div className="empty-icon">◌</div>
          <strong>SELECT A NODE</strong>
          <p>Click a digital-twin zone to inspect live telemetry.</p>
        </div>
      </aside>
    )
  }

  return (
    <aside className="glass-panel inspector">
      <h2>Zone Inspector</h2>
      <div className="inspector-title">{zone.zone}</div>
      <div className="muted upper">{zone.zone_type}</div>
      <div className="kv"><span>People</span><span>{formatNumber(zone.people_count)}</span></div>
      <div className="kv"><span>Capacity</span><span>{formatNumber(zone.capacity)}</span></div>
      <div className="kv"><span>Density</span><span>{formatPct(zone.density, 0)}</span></div>
      <div className="kv"><span>Inflow</span><span>{formatNumber(zone.inflow)}</span></div>
      <div className="kv"><span>Outflow</span><span>{formatNumber(zone.outflow)}</span></div>
      <div className="kv">
        <span>Risk</span>
        <span style={{ color: riskColor(zone.risk_level) }}>{zone.risk_score} {zone.risk_level}</span>
      </div>
      <div className="kv"><span>Speed</span><span>{displayOrNA(zone.avg_speed, (v) => Number(v).toFixed(2))}</span></div>
      {onFindRoute && (
        <button type="button" className="ghost-btn full" onClick={onFindRoute}>
          Use in routing
        </button>
      )}
    </aside>
  )
}
