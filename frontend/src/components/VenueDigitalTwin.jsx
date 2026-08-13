import { Suspense, useMemo, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid } from '@react-three/drei'
import { layoutVenueNodes } from '../utils/venue3d'
import {
  CrowdParticles,
  RoutePath,
  VenueEdges,
  VenueNode,
} from './VenueDigitalTwinScene'

function TwinScene({
  graph,
  zones,
  selectedZoneId,
  onSelectZone,
  routePath,
  viewMode,
}) {
  const controlsRef = useRef()
  const [hovered, setHovered] = useState(null)

  const zoneMap = useMemo(() => {
    const map = {}
    for (const z of zones || []) map[z.zone] = z
    return map
  }, [zones])

  const positions = useMemo(() => layoutVenueNodes(graph?.nodes || []), [graph])

  const routeSet = useMemo(() => {
    const set = new Set()
    if (routePath && routePath.length > 1) {
      for (let i = 0; i < routePath.length - 1; i += 1) {
        set.add(`${routePath[i]}|${routePath[i + 1]}`)
        set.add(`${routePath[i + 1]}|${routePath[i]}`)
      }
    }
    return set
  }, [routePath])

  return (
    <>
      <color attach="background" args={['#060a12']} />
      <ambientLight intensity={0.55} />
      <directionalLight position={[8, 16, 6]} intensity={1.1} castShadow />
      <pointLight position={[-6, 8, -4]} intensity={0.4} color="#38bdf8" />

      <Grid
        infiniteGrid
        fadeDistance={40}
        sectionSize={3}
        cellSize={1}
        sectionColor="#1e293b"
        cellColor="#111827"
        position={[0, 0, 0]}
      />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]} receiveShadow>
        <planeGeometry args={[60, 60]} />
        <meshStandardMaterial color="#070d16" transparent opacity={0.85} />
      </mesh>

      <VenueEdges edges={graph?.edges || []} positions={positions} routeSet={routeSet} />
      <RoutePath positions={positions} path={routePath} />

      {(graph?.nodes || []).map((node) => {
        const pos = positions[node.id]
        if (!pos) return null
        const zone = zoneMap[node.id]
        return (
          <group key={node.id}>
            <VenueNode
              id={node.id}
              zoneType={node.zone_type}
              position={[pos.x, pos.y, pos.z]}
              zone={zone}
              selected={selectedZoneId === node.id}
              hovered={hovered === node.id}
              onSelect={onSelectZone}
              onHover={setHovered}
            />
            <CrowdParticles
              position={[pos.x, pos.y, pos.z]}
              peopleCount={zone?.people_count}
              density={zone?.density}
              riskLevel={zone?.risk_level}
            />
          </group>
        )
      })}

      <OrbitControls
        ref={controlsRef}
        makeDefault
        enablePan
        minDistance={6}
        maxDistance={36}
        maxPolarAngle={viewMode === 'top' ? 0.25 : Math.PI / 2.15}
        target={[0, 0, 0]}
      />
    </>
  )
}

export default function VenueDigitalTwin({
  graph,
  zones,
  selectedZoneId,
  onSelectZone,
  routePath,
}) {
  const [viewMode, setViewMode] = useState('3d')
  const [viewKey, setViewKey] = useState(0)

  const hasGraph = (graph?.nodes || []).length > 0

  return (
    <div className="twin-panel">
      <div className="twin-head">
        <div>
          <h2>Venue Digital Twin</h2>
          <p>Live crowd flow · risk-linked nodes</p>
        </div>
        <div className="twin-controls" role="group" aria-label="Camera controls">
          <button type="button" className={viewMode === '3d' ? 'active' : ''} onClick={() => { setViewMode('3d'); setViewKey((k) => k + 1) }}>3D</button>
          <button type="button" className={viewMode === 'top' ? 'active' : ''} onClick={() => { setViewMode('top'); setViewKey((k) => k + 1) }}>TOP</button>
          <button type="button" onClick={() => setViewKey((k) => k + 1)}>RESET</button>
          <button type="button" onClick={() => { setViewMode('3d'); setViewKey((k) => k + 1) }}>FIT</button>
        </div>
      </div>

      <div className="twin-canvas-wrap">
        {!hasGraph ? (
          <div className="empty-state center">
            <div className="empty-icon">◌</div>
            <strong>WAITING FOR VENUE GRAPH</strong>
            <p>Select a venue or run a simulation to load the digital twin.</p>
          </div>
        ) : (
          <Canvas
            key={`${viewKey}-${viewMode}`}
            shadows
            dpr={[1, 1.75]}
            camera={{ position: viewMode === 'top' ? [0, 22, 0.01] : [14, 11, 14], fov: 45 }}
            gl={{ antialias: true, powerPreference: 'high-performance' }}
          >
            <Suspense fallback={null}>
              <TwinScene
                graph={graph}
                zones={zones}
                selectedZoneId={selectedZoneId}
                onSelectZone={onSelectZone}
                routePath={routePath}
                viewMode={viewMode}
              />
            </Suspense>
          </Canvas>
        )}
      </div>

      <div className="twin-legend">
        <span><i className="dot low" /> LOW</span>
        <span><i className="dot med" /> MEDIUM</span>
        <span><i className="dot high" /> HIGH</span>
        <span><i className="dot crit" /> CRITICAL</span>
        <span><i className="dot flow" /> CROWD FLOW</span>
        <span>GATE · CORRIDOR · CONCESSION · EVENT · EMERGENCY EXIT</span>
      </div>
    </div>
  )
}
