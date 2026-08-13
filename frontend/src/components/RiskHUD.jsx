import { formatNumber, riskColor, riskDot } from '../utils/format'

export default function RiskHUD({ stats, highRiskZones, onSelectZone }) {
  const score = stats?.overall_risk_score
  const level = stats?.overall_risk_level

  return (
    <aside className="glass-panel risk-hud">
      <h2>Crowd Risk</h2>
      {score == null ? (
        <div className="empty-state compact">
          <div className="empty-icon">◌</div>
          <strong>WAITING FOR SIMULATION</strong>
          <p>Run a scenario to populate live risk intelligence.</p>
        </div>
      ) : (
        <>
          <div className="risk-orb" style={{ borderColor: riskColor(level) }}>
            <div className="risk-number" style={{ color: riskColor(level) }}>{formatNumber(score)}</div>
            <div className="risk-level-text" style={{ color: riskColor(level) }}>{level} {riskDot(level)}</div>
          </div>
          <div className="risk-track">
            <div className="risk-fill" style={{ width: `${Math.min(100, score)}%`, background: riskColor(level) }} />
          </div>
          <div className="section-label">Critical Zones</div>
          {(highRiskZones || []).length === 0 && <p className="muted">No high-risk zones in current snapshot.</p>}
          {(highRiskZones || []).map((z) => (
            <button type="button" key={z.zone} className="risk-row" onClick={() => onSelectZone?.(z.zone)}>
              <span>{riskDot(z.risk_level)} {z.zone}</span>
              <span style={{ color: riskColor(z.risk_level) }}>{z.risk_score}</span>
            </button>
          ))}
        </>
      )}
    </aside>
  )
}
