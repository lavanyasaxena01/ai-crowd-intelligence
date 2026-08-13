import { useEffect, useMemo } from 'react'
import ReactFlow, {
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
  useEdgesState,
  useNodesState,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { formatNumber, formatPct, riskColor } from '../utils/format'

function ZoneNode({ data, selected }) {
  return (
    <div
      className={`zone-node${selected ? ' selected' : ''}`}
      style={{ borderLeft: `3px solid ${riskColor(data.risk_level)}` }}
      role="button"
      tabIndex={0}
      aria-label={`Zone ${data.label}, risk ${data.risk_level}`}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="zn-id">{data.label}</div>
      <div className="zn-meta">{data.zone_type}</div>
      <div className="zn-meta">
        {data.people_count ?? 0}/{data.capacity ?? '—'} · {data.risk_score ?? '—'}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  )
}

const nodeTypes = { zone: ZoneNode }

function layoutNodes(graphNodes) {
  const typeOrder = {
    gate: 0,
    entry: 0,
    corridor: 1,
    waiting_area: 1,
    food_court: 2,
    event_zone: 2,
    exit: 3,
  }
  const columns = [[], [], [], []]
  for (const n of graphNodes) {
    const col = typeOrder[n.zone_type] ?? 1
    columns[col].push(n)
  }
  const positioned = []
  columns.forEach((col, x) => {
    col.forEach((n, y) => {
      positioned.push({
        id: n.id,
        type: 'zone',
        position: { x: 36 + x * 210, y: 24 + y * 100 },
        data: {
          label: n.id,
          zone_type: n.zone_type,
          capacity: n.capacity,
          people_count: n.people_count ?? 0,
          risk_score: n.risk_score ?? 0,
          risk_level: n.risk_level || 'LOW',
        },
        selected: Boolean(n.selected),
      })
    })
  })
  return positioned
}

export default function VenueMap({ graph, zones, selectedZoneId, onSelectZone, routePath }) {
  const zoneMap = useMemo(() => {
    const map = {}
    for (const z of zones || []) map[z.zone] = z
    return map
  }, [zones])

  const enrichedNodes = useMemo(() => {
    const base = graph?.nodes || []
    return base.map((n) => {
      const z = zoneMap[n.id]
      return {
        ...n,
        people_count: z?.people_count ?? 0,
        risk_score: z?.risk_score ?? 0,
        risk_level: z?.risk_level || 'LOW',
        density: z?.density,
        inflow: z?.inflow,
        outflow: z?.outflow,
        avg_speed: z?.avg_speed,
        selected: n.id === selectedZoneId,
      }
    })
  }, [graph, zoneMap, selectedZoneId])

  const initialNodes = useMemo(() => layoutNodes(enrichedNodes), [enrichedNodes])
  const initialEdges = useMemo(() => {
    const routeSet = new Set()
    const hasRoute = Array.isArray(routePath) && routePath.length > 1
    if (hasRoute) {
      for (let i = 0; i < routePath.length - 1; i += 1) {
        routeSet.add(`${routePath[i]}|${routePath[i + 1]}`)
        routeSet.add(`${routePath[i + 1]}|${routePath[i]}`)
      }
    }
    return (graph?.edges || []).map((e, idx) => {
      const onRoute = routeSet.has(`${e.source}|${e.target}`)
      return {
        id: `e-${idx}-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        animated: onRoute,
        style: {
          stroke: onRoute ? '#38bdf8' : hasRoute ? '#1e293b' : '#334155',
          strokeWidth: onRoute ? 2.8 : 1.1,
          opacity: hasRoute && !onRoute ? 0.35 : 1,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: onRoute ? '#38bdf8' : '#334155',
          width: 14,
          height: 14,
        },
      }
    })
  }, [graph, routePath])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  useEffect(() => {
    setNodes(initialNodes)
  }, [initialNodes, setNodes])

  useEffect(() => {
    setEdges(initialEdges)
  }, [initialEdges, setEdges])

  const selected = enrichedNodes.find((n) => n.id === selectedZoneId)

  return (
    <div>
      <div className="map-wrap" aria-label="Venue map">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.35}
          maxZoom={1.6}
          onNodeClick={(_, node) => onSelectZone?.(node.id)}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#1e293b" gap={18} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      {selected && (
        <div className="detail-box" aria-live="polite">
          <div className="detail-title">ZONE DETAILS · {selected.id}</div>
          <div>Type <strong>{selected.zone_type}</strong></div>
          <div>People <strong>{formatNumber(selected.people_count)}</strong></div>
          <div>Capacity <strong>{formatNumber(selected.capacity)}</strong></div>
          <div>Density <strong>{formatPct(selected.density, 0)}</strong></div>
          <div>Inflow <strong>{formatNumber(selected.inflow)}</strong></div>
          <div>Outflow <strong>{formatNumber(selected.outflow)}</strong></div>
          <div>
            Risk{' '}
            <strong style={{ color: riskColor(selected.risk_level) }}>
              {selected.risk_score} {selected.risk_level}
            </strong>
          </div>
        </div>
      )}
    </div>
  )
}
