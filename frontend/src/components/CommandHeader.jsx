export default function CommandHeader({ online, modelLoaded, simulatorReady, onRefresh }) {
  return (
    <header className="cc-header">
      <div className="cc-brand">
        <div className="brand-orb" aria-hidden="true" />
        <div>
          <p className="brand-kicker">AI-POWERED CROWD MONITORING & PREDICTION</p>
          <h1>CROWD INTELLIGENCE<br /><span>COMMAND CENTER</span></h1>
        </div>
      </div>
      <div className="cc-status-block">
        <div className="status-pills" aria-label="System status">
          <span className={`pill ${online ? 'on' : 'off'}`}>● API {online ? 'CONNECTED' : 'OFFLINE'}</span>
          <span className={`pill ${modelLoaded ? 'on' : 'warn'}`}>● MODEL {modelLoaded ? 'LOADED' : 'UNAVAILABLE'}</span>
          <span className={`pill ${simulatorReady ? 'on' : 'off'}`}>● SIMULATOR {simulatorReady ? 'READY' : 'DOWN'}</span>
        </div>
        <button type="button" className="ghost-btn" onClick={onRefresh} aria-label="Refresh connection">Refresh</button>
      </div>
    </header>
  )
}
