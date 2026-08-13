import {
  Line,
  LineChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from 'recharts'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload || {}
  return (
    <div className="chart-tooltip">
      <div>{label}</div>
      {row.density_pct != null && <div>Density: {row.density_pct}%</div>}
      {row.predicted_density_pct != null && <div>Predicted: {row.predicted_density_pct}%</div>}
      <div>Risk: {row.risk_score ?? 'N/A'}</div>
    </div>
  )
}

export default function ForecastChart({ forecast }) {
  const data = (forecast || []).map((p) => ({
    label: p.label,
    density_pct: p.density_pct,
    predicted_density_pct: p.predicted_density_pct,
    risk_score: p.risk_score,
  }))

  if (!data.length) {
    return (
      <div className="empty-state compact">
        <div className="empty-icon">◌</div>
        <strong>NO FORECAST AVAILABLE</strong>
        <p>Run a simulation to generate predictive crowd data.</p>
      </div>
    )
  }

  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#243041" strokeDasharray="3 3" />
          <XAxis dataKey="label" stroke="#94a3b8" tick={{ fontSize: 11 }} />
          <YAxis
            stroke="#94a3b8"
            tick={{ fontSize: 11 }}
            unit="%"
            domain={[0, (max) => Math.max(100, Math.ceil((max || 0) / 10) * 10)]}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <ReferenceLine y={100} stroke="#ef4444" strokeDasharray="4 4" label={{ value: 'Critical', fill: '#fca5a5', fontSize: 10 }} />
          <Line type="monotone" dataKey="density_pct" stroke="#38bdf8" strokeWidth={2} dot={{ r: 3 }} name="Current Density" connectNulls />
          <Line type="monotone" dataKey="predicted_density_pct" stroke="#f59e0b" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 3 }} name="Predicted Density" connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
