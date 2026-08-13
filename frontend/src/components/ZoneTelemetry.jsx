import { useMemo, useState } from 'react'
import { formatPct, riskColor } from '../utils/format'

export default function ZoneTelemetry({ zones, selectedZoneId, onSelectZone }) {
  const [sortKey, setSortKey] = useState('risk_score')
  const [filter, setFilter] = useState('')

  const rows = useMemo(() => {
    let list = [...(zones || [])]
    if (filter.trim()) {
      const q = filter.trim().toLowerCase()
      list = list.filter((z) => z.zone.toLowerCase().includes(q) || (z.zone_type || '').includes(q))
    }
    list.sort((a, b) => {
      if (sortKey === 'zone') return a.zone.localeCompare(b.zone)
      if (sortKey === 'density') return b.density - a.density
      if (sortKey === 'people_count') return b.people_count - a.people_count
      return b.risk_score - a.risk_score
    })
    return list
  }, [zones, sortKey, filter])

  return (
    <div className="glass-panel">
      <div className="panel-head">
        <h2>Zone Telemetry</h2>
        <div className="telemetry-tools">
          <input
            type="search"
            placeholder="Filter zones"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            aria-label="Filter zones"
          />
          <select value={sortKey} onChange={(e) => setSortKey(e.target.value)} aria-label="Sort telemetry">
            <option value="risk_score">Risk</option>
            <option value="density">Density</option>
            <option value="people_count">People</option>
            <option value="zone">Zone</option>
          </select>
        </div>
      </div>
      {!rows.length ? (
        <div className="empty-state compact">
          <div className="empty-icon">◌</div>
          <strong>NO TELEMETRY YET</strong>
          <p>Run a simulation to populate zone intelligence.</p>
        </div>
      ) : (
        <div className="table-wrap premium">
          <table className="data">
            <thead>
              <tr>
                <th>Zone</th>
                <th>Type</th>
                <th>People</th>
                <th>Capacity</th>
                <th>Density</th>
                <th>Inflow</th>
                <th>Outflow</th>
                <th>Risk</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((z) => (
                <tr
                  key={z.zone}
                  className={`${selectedZoneId === z.zone ? 'row-selected' : ''} ${['HIGH', 'CRITICAL'].includes(z.risk_level) ? 'row-alert' : ''}`}
                  onClick={() => onSelectZone?.(z.zone)}
                >
                  <td>{z.zone}</td>
                  <td>{z.zone_type}</td>
                  <td className="mono">{z.people_count}</td>
                  <td className="mono">{z.capacity}</td>
                  <td className="mono">{formatPct(z.density, 0)}</td>
                  <td className="mono">{z.inflow}</td>
                  <td className="mono">{z.outflow}</td>
                  <td className="mono" style={{ color: riskColor(z.risk_level) }}>{z.risk_score}</td>
                  <td style={{ color: riskColor(z.risk_level) }}>{z.status || z.risk_level}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
