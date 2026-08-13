import { formatNumber, formatPct } from '../utils/format'

export default function KPIStrip({ stats, totalPeople }) {
  const items = [
    { label: 'Total Crowd', value: formatNumber(stats?.total_crowd ?? totalPeople) },
    { label: 'Avg Density', value: formatPct(stats?.avg_density, 0) },
    { label: 'Inflow / min', value: formatNumber(stats?.inflow_per_min, 1) },
    { label: 'Outflow / min', value: formatNumber(stats?.outflow_per_min, 1) },
    { label: 'Active Alerts', value: formatNumber(stats?.active_alerts), alert: Boolean(stats?.active_alerts) },
  ]

  return (
    <section className="kpi-strip" aria-label="Live crowd metrics">
      {items.map((item) => (
        <div className="kpi-tile" key={item.label}>
          <span>{item.label}</span>
          <strong className={item.alert ? 'alert' : ''}>{item.value}</strong>
        </div>
      ))}
    </section>
  )
}
