import { displayOrNA, formatPct } from '../utils/format'

export default function WhatIfPanel({
  currentArrival,
  whatIfRate,
  onRate,
  onRun,
  loading,
  disabled,
  whatIfResult,
}) {
  return (
    <div className="glass-panel">
      <h2>What-If Simulator</h2>
      {!currentArrival && !whatIfResult ? (
        <div className="empty-state compact">
          <div className="empty-icon">◌</div>
          <strong>WAITING FOR BASELINE</strong>
          <p>Run a simulation before exploring alternate arrival pressure.</p>
        </div>
      ) : (
        <>
          <div className="kv"><span>Current Arrival Rate</span><span>{displayOrNA(currentArrival)}</span></div>
          <div className="field">
            <label htmlFor="whatif">Test Arrival Rate ({whatIfRate})</label>
            <input id="whatif" type="range" min={0} max={40} step={0.5} value={whatIfRate} onChange={(e) => onRate(e.target.value)} />
          </div>
          <button type="button" className="run-btn compact" disabled={!!loading || disabled} onClick={onRun}>
            RUN WHAT-IF
          </button>
        </>
      )}

      {whatIfResult && (
        <div className="whatif-grid">
          <div>
            <div className="section-label">Current</div>
            <div className="kv"><span>Risk</span><span>{whatIfResult.current.risk_score}</span></div>
            <div className="kv"><span>Density</span><span>{formatPct(whatIfResult.current.density ?? whatIfResult.current.stats?.avg_density, 0)}</span></div>
            <div className="kv"><span>ETA</span><span>{displayOrNA(whatIfResult.current.time_to_bottleneck, (v) => `${v} steps`)}</span></div>
          </div>
          <div>
            <div className="section-label">What-If</div>
            <div className="kv"><span>Risk</span><span>{whatIfResult.what_if.risk_score}</span></div>
            <div className="kv"><span>Density</span><span>{formatPct(whatIfResult.what_if.density ?? whatIfResult.what_if.stats?.avg_density, 0)}</span></div>
            <div className="kv"><span>ETA</span><span>{displayOrNA(whatIfResult.what_if.time_to_bottleneck, (v) => `${v} steps`)}</span></div>
          </div>
          <div className="full">
            <div className="kv"><span>Risk Δ</span><span>{whatIfResult.change.risk_delta > 0 ? '+' : ''}{whatIfResult.change.risk_delta}</span></div>
            <div className="kv">
              <span>Density Δ</span>
              <span>{displayOrNA(whatIfResult.change.density_delta, (v) => `${v > 0 ? '+' : ''}${(Number(v) * 100).toFixed(0)}%`)}</span>
            </div>
            <div className="kv"><span>ETA Δ</span><span>{displayOrNA(whatIfResult.change.eta_delta, (v) => `${v > 0 ? '+' : ''}${v}`)}</span></div>
          </div>
        </div>
      )}
    </div>
  )
}
