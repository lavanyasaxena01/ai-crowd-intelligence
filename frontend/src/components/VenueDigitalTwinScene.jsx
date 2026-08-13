import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { Html } from '@react-three/drei'
import { nodeGeometryKind, particleCountForZone, riskAccent } from '../utils/venue3d'
import { formatNumber, formatPct } from '../utils/format'

function NodeMesh({ kind, color, selected, critical }) {
  const scale = selected ? 1.15 : 1
  const emissive = critical ? color : '#0b1220'
  const intensity = critical ? 0.55 : selected ? 0.35 : 0.15

  if (kind === 'sphere') {
    return (
      <mesh scale={scale} castShadow>
        <sphereGeometry args={[0.55, 24, 24]} />
        <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={intensity} metalness={0.35} roughness={0.35} />
      </mesh>
    )
  }
  if (kind === 'box') {
    return (
      <mesh scale={scale} castShadow>
        <boxGeometry args={[1.1, 0.45, 1.6]} />
        <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={intensity} metalness={0.25} roughness={0.4} />
      </mesh>
    )
  }
  if (kind === 'octahedron') {
    return (
      <mesh scale={scale} castShadow rotation={[0, Math.PI / 4, 0]}>
        <octahedronGeometry args={[0.6, 0]} />
        <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={intensity} metalness={0.4} roughness={0.3} />
      </mesh>
    )
  }
  return (
    <mesh scale={scale} castShadow>
      <cylinderGeometry args={[0.7, 0.7, 0.35, 6]} />
      <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={intensity} metalness={0.3} roughness={0.35} />
    </mesh>
  )
}

function PulseRing({ color, active }) {
  const ref = useRef()
  useFrame(({ clock }) => {
    if (!ref.current || !active) return
    const t = clock.getElapsedTime()
    const s = 1.2 + Math.sin(t * 3) * 0.15
    ref.current.scale.set(s, s, s)
    ref.current.material.opacity = 0.25 + Math.sin(t * 3) * 0.15
  })
  if (!active) return null
  return (
    <mesh ref={ref} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.05, 0]}>
      <ringGeometry args={[0.85, 1.05, 32]} />
      <meshBasicMaterial color={color} transparent opacity={0.35} side={THREE.DoubleSide} />
    </mesh>
  )
}

export function VenueNode({
  id,
  zoneType,
  position,
  zone,
  selected,
  onSelect,
  hovered,
  onHover,
}) {
  const color = riskAccent(zone?.risk_level || 'LOW')
  const kind = nodeGeometryKind(zoneType)
  const critical = (zone?.risk_level || '') === 'CRITICAL' || (zone?.risk_level || '') === 'HIGH'
  const [x, y, z] = position

  return (
    <group position={[x, y, z]}>
      <PulseRing color={color} active={critical} />
      <mesh
        position={[0, 0.02, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        onClick={(e) => {
          e.stopPropagation()
          onSelect?.(id)
        }}
        onPointerOver={(e) => {
          e.stopPropagation()
          onHover?.(id)
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          onHover?.(null)
          document.body.style.cursor = 'default'
        }}
      >
        <circleGeometry args={[0.95, 24]} />
        <meshBasicMaterial color={color} transparent opacity={0.12} />
      </mesh>
      <group
        onClick={(e) => {
          e.stopPropagation()
          onSelect?.(id)
        }}
        onPointerOver={(e) => {
          e.stopPropagation()
          onHover?.(id)
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          onHover?.(null)
          document.body.style.cursor = 'default'
        }}
      >
        <NodeMesh kind={kind} color={color} selected={selected || hovered} critical={critical} />
      </group>
      <Html position={[0, 1.15, 0]} center distanceFactor={14} style={{ pointerEvents: 'none' }}>
        <div className={`twin-label${selected ? ' active' : ''}`}>
          <strong>{id}</strong>
          {zone && <span>{zone.risk_score ?? '—'} {zone.risk_level || ''}</span>}
        </div>
      </Html>
      {hovered && zone && (
        <Html position={[0, 2.1, 0]} center distanceFactor={12} style={{ pointerEvents: 'none' }}>
          <div className="twin-tooltip">
            <div className="tt-title">{id}</div>
            <div>People {formatNumber(zone.people_count)}</div>
            <div>Capacity {formatNumber(zone.capacity)}</div>
            <div>Density {formatPct(zone.density, 0)}</div>
            <div>Inflow {formatNumber(zone.inflow)}</div>
            <div>Outflow {formatNumber(zone.outflow)}</div>
            <div>Risk {zone.risk_score} {zone.risk_level}</div>
          </div>
        </Html>
      )}
    </group>
  )
}

export function CrowdParticles({ position, peopleCount, density, riskLevel }) {
  const count = particleCountForZone(peopleCount, density)
  const meshRef = useRef()
  const color = riskAccent(riskLevel || 'LOW')

  const { offsets, phases } = useMemo(() => {
    const o = []
    const p = []
    for (let i = 0; i < count; i += 1) {
      const a = (i / Math.max(count, 1)) * Math.PI * 2
      const r = 0.25 + (i % 5) * 0.12
      o.push([Math.cos(a) * r, 0.15 + (i % 3) * 0.05, Math.sin(a) * r * 0.8])
      p.push(Math.random() * Math.PI * 2)
    }
    return { offsets: o, phases: p }
  }, [count])

  const dummy = useMemo(() => new THREE.Object3D(), [])

  useFrame(({ clock }) => {
    if (!meshRef.current || count === 0) return
    const t = clock.getElapsedTime()
    for (let i = 0; i < count; i += 1) {
      const [ox, oy, oz] = offsets[i]
      const wobble = Math.sin(t * 1.6 + phases[i]) * 0.08
      dummy.position.set(ox + wobble, oy + Math.abs(Math.sin(t * 2 + phases[i])) * 0.05, oz)
      dummy.scale.setScalar(0.08 + (density || 0) * 0.04)
      dummy.updateMatrix()
      meshRef.current.setMatrixAt(i, dummy.matrix)
    }
    meshRef.current.instanceMatrix.needsUpdate = true
  })

  if (count === 0) return null

  return (
    <group position={position}>
      <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
        <sphereGeometry args={[1, 8, 8]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.35} />
      </instancedMesh>
    </group>
  )
}

export function RoutePath({ positions, path = [] }) {
  const points = useMemo(() => {
    if (!path || path.length < 2) return null
    const pts = path
      .map((id) => positions[id])
      .filter(Boolean)
      .map((p) => new THREE.Vector3(p.x, p.y + 0.55, p.z))
    if (pts.length < 2) return null
    return pts
  }, [positions, path])

  if (!points) return null

  return (
    <group>
      {points.slice(0, -1).map((from, i) => {
        const to = points[i + 1]
        const mid = from.clone().lerp(to, 0.5)
        const dir = to.clone().sub(from)
        const len = dir.length()
        const quat = new THREE.Quaternion().setFromUnitVectors(
          new THREE.Vector3(0, 1, 0),
          dir.clone().normalize(),
        )
        return (
          <mesh key={`seg-${i}`} position={mid.toArray()} quaternion={quat}>
            <cylinderGeometry args={[0.06, 0.06, len, 8]} />
            <meshStandardMaterial color="#38bdf8" emissive="#0284c7" emissiveIntensity={0.7} />
          </mesh>
        )
      })}
    </group>
  )
}

export function VenueEdges({ edges = [], positions, routeSet }) {
  return (
    <group>
      {edges.map((e, idx) => {
        const a = positions[e.source]
        const b = positions[e.target]
        if (!a || !b) return null
        const from = new THREE.Vector3(a.x, 0.2, a.z)
        const to = new THREE.Vector3(b.x, 0.2, b.z)
        const mid = from.clone().lerp(to, 0.5)
        const dir = to.clone().sub(from)
        const len = dir.length()
        const onRoute = routeSet?.has(`${e.source}|${e.target}`)
        const quat = new THREE.Quaternion().setFromUnitVectors(
          new THREE.Vector3(0, 1, 0),
          dir.clone().normalize(),
        )
        return (
          <mesh key={`edge-${idx}`} position={mid.toArray()} quaternion={quat}>
            <cylinderGeometry args={[onRoute ? 0.05 : 0.025, onRoute ? 0.05 : 0.025, len, 6]} />
            <meshStandardMaterial
              color={onRoute ? '#38bdf8' : '#334155'}
              transparent
              opacity={onRoute ? 0.95 : 0.35}
              emissive={onRoute ? '#0ea5e9' : '#000000'}
              emissiveIntensity={onRoute ? 0.5 : 0}
            />
          </mesh>
        )
      })}
    </group>
  )
}
