import { displayOrNA, riskColor, riskDot } from '../utils/format'

export default function InterventionPanel({
  intervention,
  interventionResult,
  loading,
  onSimulate,
}) {
  return (
    <div className="glass-panel intervention-panel">
      <h2>AI Intervention Engine</h2>
      {!intervention && (
        <div className="empty-state compact">
          <div className="empty-icon">◌</div>
          <strong>NO ACTIVE EVALUATION</strong>
          <p>Run a simulation to allow the AI intervention engine to evaluate the venue.</p>
        </div>
      )}

      {intervention?.status === 'no_alternative' && (
        <div className="empty-state compact warn">
          <strong>{intervention.message || 'No alternative gate available'}</strong>
        </div>
      )}

      {intervention?.recommended_action && (
        <>
          <div className="section-label">⚠ Bottleneck Detected</div>
          <div className="bn-title">{intervention.detected_bottleneck}</div>
          <div className="kv">
            <span>Current Risk</span>
            <span style={{ color: riskColor(intervention.current_risk_level) }}>
              {intervention.current_risk_score} {riskDot(intervention.current_risk_level)}
            </span>
          </div>
          <div className="kv"><span>Action</span><span>{intervention.recommended_action.description}</span></div>
          <div className="redirect-visual">
            <span>{intervention.recommended_action.source || intervention.recommended_action.from_gate || '—'}</span>
            <span className="arrow">→</span>
            <span>{intervention.recommended_action.target || intervention.recommended_action.to_gate || 'N/A'}</span>
          </div>
          <div className="kv">
            <span>Redirect</span>
            <span>
              {displayOrNA(
                intervention.recommended_action.percentage ?? intervention.recommended_action.redirect_percentage,
                (v) => `${v}%`,
              )}
            </span>
          </div>
          {intervention.reason && <p className="reason">{intervention.reason}</p>}
          <button type="button" className="run-btn compact" disabled={!!loading} onClick={onSimulate}>
            SIMULATE INTERVENTION
          </button>
        </>
      )}

      {interventionResult?.status === 'rejected' && (
        <div className="empty-state compact warn" style={{ marginTop: 12 }}>
          <strong>NO BENEFICIAL INTERVENTION FOUND</strong>
          <p>{interventionResult.message || 'Evaluated interventions did not reduce overall crowd risk.'}</p>
        </div>
      )}

      {interventionResult?.status === 'applied' && (
        <div className="before-after">
          <div className="ba-col">
            <span>Before</span>
            <strong style={{ color: riskColor(interventionResult.before.risk_level) }}>{interventionResult.before.risk_score}</strong>
            <div className="ba-bar"><i style={{ width: `${interventionResult.before.risk_score}%`, background: riskColor(interventionResult.before.risk_level) }} /></div>
          </div>
          <div className="ba-arrow">→</div>
          <div className="ba-col">
            <span>After</span>
            <strong style={{ color: riskColor(interventionResult.after.risk_level) }}>{interventionResult.after.risk_score}</strong>
            <div className="ba-bar"><i style={{ width: `${interventionResult.after.risk_score}%`, background: riskColor(interventionResult.after.risk_level) }} /></div>
          </div>
          <div className="ok-chip">✓ Expected to reduce congestion · −{displayOrNA(interventionResult.change?.risk_reduction_pct, (v) => `${v}%`)}</div>
        </div>
      )}
    </div>
  )
}
