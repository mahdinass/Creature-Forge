import { memo, useMemo, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Grid, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { usePlayback } from './store'
import { fallEvent, frameIndex } from './playback'
import type { RunPayload } from './types'

const PART_COLOR: Record<string, string> = { torso: '#6f8fd8', thigh: '#c9ccd6', shank: '#aab0c0', foot: '#8892a8' }
const partColor = (part: string) => PART_COLOR[part.split('_')[0]] ?? '#999'

/** Renders the recorded MuJoCo rigid-body poses. Poses are mutated on refs in useFrame (no React re-render). */
function Robot({ run }: { run: RunPayload }) {
  const meshes = useRef<(THREE.Mesh | null)[]>([])
  const rings = useRef<(THREE.Mesh | null)[]>([])
  const arrow = useRef<THREE.Group>(null)
  const geoms = run.scene.geoms
  // presentation-only: the model is planar, so draw left/right legs apart (declared by the backend)
  const lat = useMemo(() => geoms.map((g) => (g.part.endsWith('_l') ? 1 : g.part.endsWith('_r') ? -1 : 0) * run.scene.display_lateral_offset), [geoms, run.scene.display_lateral_offset])
  const torsoIdx = geoms.findIndex((g) => g.part === 'torso')
  const footIdx = useMemo(() => ['foot_l', 'foot_r'].map((p) => geoms.findIndex((g) => g.part === p)), [geoms])
  const fall = useMemo(() => fallEvent(run.events), [run.events])
  const colors = useMemo(() => geoms.map((g) => new THREE.Color(partColor(g.part))), [geoms])
  const red = useMemo(() => new THREE.Color('#e5484d'), [])
  const green = useMemo(() => new THREE.Color('#3fb97f'), [])
  const orange = useMemo(() => new THREE.Color('#f5a524'), [])

  useFrame(() => {
    const t = usePlayback.getState().simTime
    const k = frameIndex(run.time, t)
    const pos = run.frames.pos[k]
    const quat = run.frames.quat[k]
    geoms.forEach((_, i) => {
      const m = meshes.current[i]
      if (!m) return
      m.position.set(pos[i][0], pos[i][1], pos[i][2] + lat[i])
      m.quaternion.set(quat[i][0], quat[i][1], quat[i][2], quat[i][3])
    })
    const fallen = fall !== undefined && t >= fall.time
    geoms.forEach((_, i) => {
      const mat = meshes.current[i]?.material as THREE.MeshStandardMaterial | undefined
      if (!mat) return
      const f = footIdx.indexOf(i)
      if (fallen) mat.color.copy(red)
      else if (f >= 0 && run.series.foot_contact[k][f]) {
        mat.color.copy(run.series.foot_slip_speed[k][f] > 0.15 ? orange : green)
      } else mat.color.copy(colors[i])
    })
    // contact cue: ring on the ground at the measured contact point
    for (let f = 0; f < 2; f++) {
      const ring = rings.current[f]
      if (!ring) continue
      const touching = run.series.foot_contact[k][f] > 0
      ring.visible = touching
      if (touching) {
        const c = run.frames.contact_pos[k][f]
        ring.position.set(c[0], 0.004, c[2] + (f === 0 ? 1 : -1) * run.scene.display_lateral_offset)
      }
    }
    // applied push, drawn only while MuJoCo's external force is active
    if (arrow.current && run.push && torsoIdx >= 0) {
      const on = t >= run.push.time && t < run.push.time + run.push.duration
      arrow.current.visible = on
      if (on) arrow.current.position.set(pos[torsoIdx][0] - 0.55, pos[torsoIdx][1], pos[torsoIdx][2])
    }
  })

  return (
    <group>
      {geoms.map((g, i) => (
        <mesh key={`${g.part}-${i}`} ref={(el) => void (meshes.current[i] = el)} castShadow>
          {g.type === 'capsule' ? (
            <capsuleGeometry args={[g.size[0], 2 * g.size[1], 6, 16]} />
          ) : (
            <boxGeometry args={[2 * g.size[0], 2 * g.size[1], 2 * g.size[2]]} />
          )}
          <meshStandardMaterial color={partColor(g.part)} roughness={0.5} metalness={0.1} />
        </mesh>
      ))}
      {[0, 1].map((f) => (
        <mesh key={f} ref={(el) => void (rings.current[f] = el)} rotation={[-Math.PI / 2, 0, 0]} visible={false}>
          <ringGeometry args={[0.035, 0.055, 24]} />
          <meshBasicMaterial color="#3fb97f" side={THREE.DoubleSide} />
        </mesh>
      ))}
      {run.push && (
        <group ref={arrow} visible={false}>
          <mesh rotation={[0, 0, -Math.PI / 2]} position={[-0.15, 0, 0]}>
            <cylinderGeometry args={[0.015, 0.015, 0.3, 12]} />
            <meshBasicMaterial color="#f5a524" />
          </mesh>
          <mesh rotation={[0, 0, -Math.PI / 2]} position={[0.05, 0, 0]}>
            <coneGeometry args={[0.045, 0.1, 16]} />
            <meshBasicMaterial color="#f5a524" />
          </mesh>
        </group>
      )}
    </group>
  )
}

/** Keeps the orbit target (and camera) tracking the torso along x so the walk stays in view. */
function CameraRig({ run, controls }: { run: RunPayload; controls: React.RefObject<OrbitControlsImpl | null> }) {
  const camera = useThree((s) => s.camera)
  const last = useRef(0)
  useFrame(() => {
    const c = controls.current
    if (!c || !usePlayback.getState().follow) return
    const k = frameIndex(run.time, usePlayback.getState().simTime)
    const x = run.series.torso_x[k]
    const dx = x - c.target.x
    c.target.x = x
    camera.position.x += dx
    last.current = x
  })
  return null
}

function Scene({ run }: { run: RunPayload }) {
  const controls = useRef<OrbitControlsImpl>(null)
  return (
    <>
      <color attach="background" args={['#10141c']} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[3, 6, 4]} intensity={1.6} castShadow shadow-mapSize={[1024, 1024]}
        shadow-camera-left={-6} shadow-camera-right={6} shadow-camera-top={6} shadow-camera-bottom={-6} />
      {/* Backdrop floor: drawn first and writes no depth. Its two 400 m triangles, clipped at the near plane, get depth
          errors larger than the grid's 1 mm offset on some rasterisers (all of SwiftShader, intermittently Intel), which
          hid the grid; with no depth from the floor, the grid and robot never have to win against it. */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow renderOrder={-1}>
        <planeGeometry args={[400, 400]} />
        <meshStandardMaterial color="#1b2230" depthWrite={false} />
      </mesh>
      <Grid args={[400, 400]} cellSize={0.25} sectionSize={1} cellColor="#2b3548" sectionColor="#4a5a78"
        fadeDistance={25} position={[0, 0.001, 0]} infiniteGrid />
      <Robot run={run} />
      <OrbitControls ref={controls} makeDefault target={[0, 0.5, 0]} maxPolarAngle={Math.PI / 2 - 0.02}
        minDistance={0.8} maxDistance={15} />
      <CameraRig run={run} controls={controls} />
    </>
  )
}

export const Viewport = memo(function Viewport({ run, label, bare = false, className = '', closeup = false }: { run: RunPayload; label: string; bare?: boolean; className?: string; closeup?: boolean }) {
  const t = usePlayback((s) => s.simTime)
  const fall = fallEvent(run.events)
  const k = frameIndex(run.time, t)
  const h = run.series.torso_height[k]
  const fallen = fall !== undefined && t >= fall.time
  return (
    <div className={`viewport ${bare ? 'bare' : ''} ${className}`}>
      <Canvas shadows camera={{ position: closeup ? [0.45, 0.7, 1.75] : [0.5, 0.8, 2.4], fov: 45 }} dpr={[1, 2]}>
        <Scene run={run} />
      </Canvas>
      {!bare && <div className="vp-label">{label}</div>}
      {!bare && run.push && t >= run.push.time && t < run.push.time + run.push.duration && (
        // plain DOM overlay (a drei <Html> portal threw removeChild errors when a viewport unmounted)
        <div className="push-label vp-push">{run.push.force} N push</div>
      )}
      {!bare && <div className="vp-hud">
        <div>torso height <b>{h.toFixed(3)} m</b></div>
        <div>pitch <b>{(run.series.torso_pitch[k] * 57.2958).toFixed(1)}°</b></div>
        <div>feet in contact <b>{run.series.foot_contact[k].reduce((a, b) => a + b, 0)}/2</b></div>
      </div>}
      {!bare && fallen && fall && (
        <div className="vp-fall">FALL detected at sim t = {fall.time.toFixed(2)} s</div>
      )}
    </div>
  )
})
