import { riskColor } from './format'

const TYPE_LANE = {
  gate: -6,
  entry: -6,
  corridor: -2,
  waiting_area: -1,
  food_court: 2,
  event_zone: 4,
  exit: 7,
}

/**
 * Layout backend graph nodes into 3D positions using zone_type lanes.
 * Topology (edges) stays from backend; only visual placement is derived.
 */
export function layoutVenueNodes(graphNodes = []) {
  const buckets = {}
  for (const node of graphNodes) {
    const lane = TYPE_LANE[node.zone_type] ?? 0
    if (!buckets[lane]) buckets[lane] = []
    buckets[lane].push(node)
  }

  const positions = {}
  Object.entries(buckets).forEach(([laneStr, list]) => {
    const lane = Number(laneStr)
    const count = list.length
    list.forEach((node, index) => {
      const spread = (index - (count - 1) / 2) * 3.2
      positions[node.id] = {
        x: lane,
        y: 0.35,
        z: spread,
      }
    })
  })
  return positions
}

export function nodeGeometryKind(zoneType) {
  switch (zoneType) {
    case 'gate':
    case 'entry':
      return 'sphere'
    case 'corridor':
    case 'waiting_area':
      return 'box'
    case 'exit':
      return 'octahedron'
    case 'food_court':
    case 'event_zone':
    default:
      return 'cylinder'
  }
}

export function riskAccent(level) {
  return riskColor(level)
}

export function particleCountForZone(peopleCount, density) {
  const byPeople = Math.min(48, Math.max(0, Math.round((peopleCount || 0) / 8)))
  const byDensity = Math.min(24, Math.round((density || 0) * 20))
  return Math.min(56, Math.max(byPeople, byDensity))
}
