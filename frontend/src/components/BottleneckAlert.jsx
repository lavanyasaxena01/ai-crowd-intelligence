import { displayOrNA, formatPct, riskColor } from '../utils/format'

export default function BottleneckAlert({ bottleneck }) {
  if (!bottleneck) {
    return (
      <div className="glass-panel">
        <div className="empty-state compact">
          <div className="empty-icon">◌</div>
          <strong>NO BOTTLENECK DATA</strong>
          <p>Run a simulation to allow prediction.</p>
        </div>
      </div>
    )
  }

  if (!bottleneck.is_critical) {
    return (
      <div className="alert-banner ok">
        <strong>✓ NO CRITICAL BOTTLENECK PREDICTED</strong>
        <span>Watch zone: {bottleneck.zone}</span>
      </div>
    )
  }

  return (
    <div className="alert-banner critical pulse">
      <div>
        <div className="section-label">⚠ Bottleneck Predicted</div>
        <div className="bn-title">{bottleneck.zone}</div>
        <p>Critical congestion expected in {displayOrNA(bottleneck.time_to_bottleneck, (v) => `${v} steps`)}</p>
      </div>
      <div className="bn-metrics">
        <div>
          <span>Predicted Density</span>
          <strong>{displayOrNA(bottleneck.predicted_density, (v) => formatPct(v, 0))}</strong>
        </div>
        <div>
          <span>Risk</span>
          <strong style={{ color: riskColor(bottleneck.risk_level) }}>
            {bottleneck.risk_score} {bottleneck.risk_level}
          </strong>
        </div>
      </div>
    </div>
  )
}
