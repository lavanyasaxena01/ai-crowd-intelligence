export function riskColor(level) {
  switch ((level || '').toUpperCase()) {
    case 'CRITICAL':
      return '#ef4444'
    case 'HIGH':
      return '#f97316'
    case 'MEDIUM':
      return '#eab308'
    case 'LOW':
    default:
      return '#22c55e'
  }
}

export function riskDot(level) {
  switch ((level || '').toUpperCase()) {
    case 'CRITICAL':
      return '🔴'
    case 'HIGH':
      return '🟠'
    case 'MEDIUM':
      return '🟡'
    case 'LOW':
    default:
      return '🟢'
  }
}

export function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A'
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })
}

export function formatPct(density, digits = 0) {
  if (density === null || density === undefined || Number.isNaN(Number(density))) return 'N/A'
  return `${(Number(density) * 100).toFixed(digits)}%`
}

export function displayOrNA(value, formatter) {
  if (value === null || value === undefined || value === '') return 'N/A'
  return formatter ? formatter(value) : String(value)
}
