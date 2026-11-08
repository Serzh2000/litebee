import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import type { LiveDrone } from '../../../main/link'
import { cellInArea, type Area } from '@core/area'
import { colorAt, positionAt, type Rgb, type Show } from '@core/show'
import { css as rgbCss, isLit, luminance } from '../lib/color'
import { batteryLevel, isAlive } from '../state/useLink'
import { useTheme } from '../state/useTheme'
import { TAG_CM, TAGS } from './MatChart'
import './Mat3D.css'
import { tr } from '@core/i18n'

/**
 * The simulation in three dimensions: the mat as a floor of 12 x 12 cells, the drones as the model of the real LiteBee
 * Wing (assets/litebee_fm10), the LED lit in its colour, the propellers turning while the drone is in the air.
 *
 * World coordinates are the ones of the show (cm; x along the columns, y along the rows, z up). In the scene x stays,
 * the height is the vertical axis and y runs away from the viewer: north of the map is -Z.
 */
const SHEET = 480
const MODEL_URL = './models/litebee_fm10.glb'
const MODEL_SCALE = 100 * 1.5 // the model is in metres; drawn half as large again so that it can be seen on a mat of 40 cm cells
const FLOOR_PX = 2048
/** ?closeup=1 (for screenshots): the camera stays close to the selected drone */
const CLOSE_UP = new URLSearchParams(window.location.search).get('closeup') === '1'

interface Props {
  show: Show
  t: number
  selected: number | null
  onSelect: (n: number | null) => void
  area: Area
  size: { width: number; height: number }
  /** the real drones on the link: a ring and a tag at the place they report */
  live?: LiveDrone[]
  /** a drone was dragged to a cell: it now starts there */
  onMove?: (drone: number, cell: number) => void
}

let template: Promise<{ root: THREE.Group; lift: number }> | null = null

/** The model, loaded once: the propellers get a pivot at their hub so that they turn about it, the feet stand on zero. */
function loadTemplate() {
  template ??= new GLTFLoader().loadAsync(MODEL_URL).then((gltf) => {
    const root = gltf.scene
    // the loader makes node names safe (spaces become underscores, dots go away): compare them in one spelling
    const norm = (n: string) => n.replace(/_/g, ' ')
    const hubs = new Map<string, THREE.Object3D>()
    root.traverse((o) => {
      if (norm(o.name).startsWith('Clear propeller hub')) hubs.set(norm(o.name).slice('Clear propeller hub'.length), o)
    })
    const props: THREE.Object3D[] = []
    root.traverse((o) => {
      if (norm(o.name).startsWith('Transparent two blade propeller')) props.push(o)
    })
    for (const p of props) {
      const hub = hubs.get(norm(p.name).slice('Transparent two blade propeller'.length))
      if (!hub) continue
      const pivot = new THREE.Group()
      pivot.name = 'spin'
      pivot.position.copy(hub.position)
      p.position.sub(hub.position)
      p.parent?.add(pivot)
      pivot.add(p)
      // a turning propeller is a blur: a pale disc, shown while the drone is in the air
      const disc = new THREE.Mesh(new THREE.CircleGeometry(0.0375, 28), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.42, depthWrite: false, side: THREE.DoubleSide }))
      disc.name = 'blur'
      disc.rotation.x = -Math.PI / 2
      disc.position.y = 0.002
      pivot.add(disc)
    }
    root.scale.setScalar(MODEL_SCALE)
    root.updateMatrixWorld(true)
    const box = new THREE.Box3().setFromObject(root)
    return { root, lift: -box.min.y }
  })
  return template
}

function floorTexture(area: Area, ink: string, rule: string, paper: string, dim: string): THREE.CanvasTexture {
  const c = document.createElement('canvas')
  c.width = c.height = FLOOR_PX
  const g = c.getContext('2d')!
  const k = FLOOR_PX / SHEET
  g.fillStyle = paper
  g.fillRect(0, 0, FLOOR_PX, FLOOR_PX)
  g.font = `bold ${Math.round(7 * k)}px sans-serif`
  g.textBaseline = 'top'
  for (let cell = 0; cell < 144; cell++) {
    const col = cell % 12
    const row = Math.floor(cell / 12)
    const x = col * 40 * k
    const y = (11 - row) * 40 * k
    if (!cellInArea(area, cell)) {
      g.fillStyle = dim
      g.fillRect(x, y, 40 * k, 40 * k)
    }
    // the marker as on the carpet of the kit: a dark square with a light pattern, its number printed under it
    const size = 22 // cm
    const s = (size / TAG_CM) * k
    g.save()
    g.translate(x + 20 * k - (size / 2) * k, y + 17 * k - (size / 2) * k)
    g.scale(s, s)
    g.globalAlpha = cellInArea(area, cell) ? 0.72 : 0.35
    g.fillStyle = ink
    g.fillRect(0, 0, TAG_CM, TAG_CM)
    g.fillStyle = paper
    g.fill(new Path2D(TAGS[cell]))
    g.restore()
    g.fillStyle = ink
    g.globalAlpha = cellInArea(area, cell) ? 0.85 : 0.4
    g.textAlign = 'center'
    g.fillText(String(cell), x + 20 * k, y + 29.5 * k)
    g.textAlign = 'start'
    g.globalAlpha = 1
  }
  g.strokeStyle = rule
  g.lineWidth = 1.5
  for (let i = 0; i <= 12; i++) {
    g.beginPath()
    g.moveTo(i * 40 * k, 0)
    g.lineTo(i * 40 * k, FLOOR_PX)
    g.moveTo(0, i * 40 * k)
    g.lineTo(FLOOR_PX, i * 40 * k)
    g.stroke()
  }
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 8
  return tex
}

/** The line bullet of a drone as a sprite: a circle in the LED colour (full for the selected drone, 70 % for the rest), its number in white, dark on a light colour. */
function plateTexture(n: number, rgb: Rgb | null, grey: string, ink: string, strong: boolean): THREE.CanvasTexture {
  const c = document.createElement('canvas')
  c.width = c.height = 96
  const g = c.getContext('2d')!
  const lit = rgb !== null && isLit(rgb)
  g.globalAlpha = strong ? 1 : 0.7
  g.fillStyle = lit ? rgbCss(rgb) : grey
  g.beginPath()
  g.arc(48, 48, 36, 0, Math.PI * 2)
  g.fill()
  g.globalAlpha = 1
  if (lit && Math.min(rgb[0], rgb[1], rgb[2]) > 200) {
    g.lineWidth = 3
    g.strokeStyle = ink
    g.stroke()
  }
  g.fillStyle = lit && luminance(rgb) > 0.45 ? '#131416' : '#ffffff'
  g.font = '600 40px "IBM Plex Sans", sans-serif'
  g.textAlign = 'center'
  g.textBaseline = 'middle'
  g.fillText(String(n), 48, 50)
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

function tagTexture(text: string, ring: string, ink: string, bg: string): THREE.CanvasTexture {
  const c = document.createElement('canvas')
  c.width = 192
  c.height = 96
  const g = c.getContext('2d')!
  g.fillStyle = bg
  g.beginPath()
  g.roundRect(6, 12, 180, 72, 14)
  g.fill()
  g.lineWidth = 6
  g.strokeStyle = ring
  g.stroke()
  g.fillStyle = ink
  g.font = 'bold 40px sans-serif'
  g.textAlign = 'center'
  g.textBaseline = 'middle'
  g.fillText(text, 96, 50)
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

const ledColor = (rgb: Rgb) => new THREE.Color(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)

interface Fleet {
  group: THREE.Group
  body: THREE.Object3D
  led: THREE.MeshStandardMaterial | null
  spins: THREE.Object3D[]
  shadow: THREE.Mesh
  plate: THREE.Sprite
  plateKey: string
}

export function Mat3D({ show, t, selected, onSelect, area, size, live = [], onMove }: Props) {
  const [modelState, setModelState] = useState<'loading' | 'ready' | 'error'>('loading')
  const host = useRef<HTMLDivElement | null>(null)
  const { theme } = useTheme()
  // what the animation loop reads: the newest props, without rebuilding the scene for each of them
  const latest = useRef({ show, t, selected, onSelect, area, theme, live, onMove })
  latest.current = { show, t, selected, onSelect, area, theme, live, onMove }
  const api = useRef<{ resize: (w: number, h: number) => void; refit: () => void } | null>(null)

  useEffect(() => {
    const el = host.current
    if (!el) return
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(38, 1, 5, 4000)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.maxPolarAngle = Math.PI * 0.47
    controls.minDistance = 60
    controls.maxDistance = 1800

    scene.add(new THREE.HemisphereLight(0xffffff, 0x8b95a1, 1.7))
    const sun = new THREE.DirectionalLight(0xffffff, 2.2)
    sun.position.set(240, 600, 520)
    scene.add(sun)

    const floor = new THREE.Mesh(new THREE.PlaneGeometry(SHEET, SHEET), new THREE.MeshBasicMaterial())
    floor.rotation.x = -Math.PI / 2
    floor.position.set(SHEET / 2 - 20, 0, -(SHEET / 2 - 20))
    scene.add(floor)

    const fleet = new Map<number, Fleet>()
    const markers = new Map<string, { group: THREE.Group; dot: THREE.Mesh; pole: THREE.Line; tag: THREE.Sprite; key: string }>()
    const route = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0x0b7285 }))
    route.frustumCulled = false
    scene.add(route)
    const ring = new THREE.Mesh(new THREE.RingGeometry(15, 18, 48), new THREE.MeshBasicMaterial({ color: 0x0b7285, side: THREE.DoubleSide }))
    ring.rotation.x = -Math.PI / 2
    scene.add(ring)
    const shadowGeo = new THREE.CircleGeometry(11, 24)

    let floorKey = ''
    let themeKey = ''
    let areaKey = ''
    let routeKey = ''
    let routeOf: unknown = null // the path the line was drawn from: a new path (a drone was moved) redraws it
    let disposed = false
    let model: Awaited<ReturnType<typeof loadTemplate>> | null = null
    void loadTemplate().then((m) => {
      if (!disposed) { model = m; setModelState('ready') }
    }).catch(() => {
      template = null
      if (!disposed) setModelState('error')
    })

    const colors = () => {
      const css = getComputedStyle(document.documentElement)
      const v = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback
      return { paper: v('--raised', '#f4f6f8'), rule: v('--border', '#e8eaec'), ink: v('--text', '#131416'), sheet: v('--surface', '#ffffff'), grey: v('--drone-grey', '#8d97a6'), accent: v('--accent', '#1b6c80') }
    }

    const refit = () => {
      const a = latest.current.area
      const cx = 40 * (a.col0 + a.cols / 2) - 20
      const cz = -(40 * (a.row0 + a.rows / 2) - 20)
      const span = Math.max(a.cols, a.rows) * 40
      controls.target.set(cx, 20, cz)
      camera.position.set(cx, span * 1.1, cz + span * 1.55)
      controls.update()
    }
    refit()

    const makeDrone = (n: number): Fleet | null => {
      if (!model) return null
      const group = new THREE.Group()
      const body = model.root.clone(true)
      body.rotation.y = Math.PI // the nose of the model looks to +Z, the nose of the show to the north (-Z)
      body.position.y = model.lift
      let led: THREE.MeshStandardMaterial | null = null
      const spins: THREE.Object3D[] = []
      body.traverse((o) => {
        if (o.name === 'spin') spins.push(o)
        const mesh = o as THREE.Mesh
        if (mesh.isMesh && (mesh.material as THREE.Material).name === 'Opal LED diffuser') {
          led = (mesh.material as THREE.MeshStandardMaterial).clone()
          mesh.material = led
        }
      })
      body.traverse((o) => {
        o.userData.drone = n
      })
      group.add(body)
      const shadow = new THREE.Mesh(shadowGeo, new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.2, depthWrite: false }))
      shadow.rotation.x = -Math.PI / 2
      scene.add(shadow)
      const plate = new THREE.Sprite(new THREE.SpriteMaterial({ transparent: true, depthTest: false }))
      plate.scale.set(18, 18, 1)
      plate.renderOrder = 10
      plate.userData.drone = n
      group.add(plate)
      scene.add(group)
      return { group, body, led, spins, shadow, plate, plateKey: '' }
    }

    // A press on a drone takes it: it follows the pointer over the floor and lands on the cell under it. A click that
    // moves nothing selects the drone under the pointer. A press anywhere else turns the camera.
    const ray = new THREE.Raycaster()
    const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)
    const hitPoint = new THREE.Vector3()
    const cellMark = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ color: 0x1b6c80, transparent: true, opacity: 0.28, depthWrite: false }))
    cellMark.rotation.x = -Math.PI / 2
    cellMark.visible = false
    scene.add(cellMark)
    let down: { x: number; y: number } | null = null
    let drag: { n: number; x: number; y: number; cell: number | null; moved: boolean } | null = null
    const aim = (e: PointerEvent) => {
      const r = renderer.domElement.getBoundingClientRect()
      ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera)
    }
    const droneAt = (e: PointerEvent): number | undefined => {
      aim(e)
      const hit = ray.intersectObjects([...fleet.values()].map((f) => f.body).concat([...fleet.values()].map((f) => f.plate)), true)[0]
      return hit?.object.userData.drone as number | undefined
    }
    const cellUnder = (e: PointerEvent): number | null => {
      aim(e)
      if (!ray.ray.intersectPlane(floorPlane, hitPoint)) return null
      const col = Math.round(hitPoint.x / 40)
      const row = Math.round(-hitPoint.z / 40)
      return col < 0 || col > 11 || row < 0 || row > 11 ? null : col + 12 * row
    }
    const onDown = (e: PointerEvent) => {
      down = { x: e.clientX, y: e.clientY }
      if (e.button !== 0 || !latest.current.onMove) return
      const n = droneAt(e)
      if (n === undefined) return
      drag = { n, x: e.clientX, y: e.clientY, cell: null, moved: false }
      controls.enabled = false // the camera stays still while a drone is carried
      try {
        renderer.domElement.setPointerCapture(e.pointerId)
      } catch {
        /* a pointer that is already gone: the drag simply follows the moves that come */
      }
      e.stopImmediatePropagation()
    }
    const onMoveEvent = (e: PointerEvent) => {
      if (!drag) {
        if (latest.current.onMove) renderer.domElement.style.cursor = droneAt(e) === undefined ? '' : 'grab'
        return
      }
      if (!drag.moved && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 5) drag.moved = true
      if (!drag.moved) return
      renderer.domElement.style.cursor = 'grabbing'
      drag.cell = cellUnder(e)
    }
    const onUp = (e: PointerEvent) => {
      const carried = drag
      drag = null
      controls.enabled = true
      cellMark.visible = false
      renderer.domElement.style.cursor = ''
      if (carried?.moved) {
        if (carried.cell !== null) latest.current.onMove?.(carried.n, carried.cell)
        return
      }
      if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4) return
      const n = droneAt(e)
      latest.current.onSelect(n === undefined || n === latest.current.selected ? null : n)
    }
    // before the camera controls, which listen on the same element
    renderer.domElement.addEventListener('pointerdown', onDown, { capture: true })
    renderer.domElement.addEventListener('pointermove', onMoveEvent)
    renderer.domElement.addEventListener('pointerup', onUp)
    const carriedNow = () => (drag?.moved && drag.cell !== null ? drag : null)

    const clock = new THREE.Clock()
    let raf = 0
    const frame = () => {
      raf = requestAnimationFrame(frame)
      const { show: sh, t: now, selected: sel, area: ar, theme: th, live: real } = latest.current
      const c = colors()

      if (th !== themeKey || JSON.stringify(ar) !== areaKey) {
        themeKey = th
        if (JSON.stringify(ar) !== areaKey && areaKey !== '') refit()
        areaKey = JSON.stringify(ar)
        const dim = th === 'dark' ? 'rgba(0,0,0,0.38)' : 'rgba(30,40,55,0.10)'
        ;(floor.material as THREE.MeshBasicMaterial).map?.dispose()
        ;(floor.material as THREE.MeshBasicMaterial).map = floorTexture(ar, c.ink, c.rule, c.paper, dim)
        floor.material.needsUpdate = true
        scene.background = new THREE.Color(c.paper)
        ;(route.material as THREE.LineBasicMaterial).color.set(c.accent)
        ;(ring.material as THREE.MeshBasicMaterial).color.set(c.accent)
        floorKey = ''
      }
      void floorKey

      const elapsed = clock.getElapsedTime()
      for (const d of sh.drones) {
        let f = fleet.get(d.number)
        if (!f) {
          f = makeDrone(d.number) ?? undefined
          if (!f) continue
          fleet.set(d.number, f)
        }
        let [x, y, z] = positionAt(d.path, now)
        const carried = carriedNow()
        if (carried && carried.n === d.number && carried.cell !== null) {
          x = 40 * (carried.cell % 12)
          y = 40 * Math.floor(carried.cell / 12)
          cellMark.position.set(x, 0.6, -y)
          cellMark.visible = true
        }
        f.group.position.set(x, Math.max(z, 0), -y)
        f.shadow.position.set(x, 0.3, -y)
        const s = Math.max(0.5, 1 - z / 260)
        f.shadow.scale.setScalar(s)
        ;(f.shadow.material as THREE.MeshBasicMaterial).opacity = 0.22 * s
        const [, rgb] = colorAt(d.steps, now)
        if (f.led) {
          const lit = isLit(rgb)
          f.led.emissive = lit ? ledColor(rgb) : new THREE.Color(0, 0, 0)
          f.led.emissiveIntensity = lit ? 2.4 : 0
        }
        const flying = z > 2
        for (const p of f.spins) {
          if (flying) p.rotation.y = elapsed * 16
          const blur = p.getObjectByName('blur')
          if (blur) blur.visible = flying
        }
        f.plate.position.set(0, 26, 0)
        const key = `${d.number}|${sel === d.number}|${isLit(rgb) ? rgb.join(',') : '-'}|${th}`
        if (key !== f.plateKey) {
          f.plateKey = key
          const mat = f.plate.material as THREE.SpriteMaterial
          mat.map?.dispose()
          mat.map = plateTexture(d.number, isLit(rgb) ? rgb : null, c.grey, c.ink, sel === d.number)
          mat.needsUpdate = true
        }
        f.group.visible = true
      }
      for (const [n, f] of fleet) {
        if (!sh.drones.some((d) => d.number === n)) {
          scene.remove(f.group, f.shadow)
          fleet.delete(n)
        }
      }

      // the selected drone: a ring on the floor under it and the route it flies
      const chosen = sh.drones.find((d) => d.number === sel)
      ring.visible = !!chosen
      route.visible = !!chosen
      if (chosen) {
        const [x, y] = positionAt(chosen.path, now)
        ring.position.set(x, 0.6, -y)
        if (CLOSE_UP) {
          const [, , z] = positionAt(chosen.path, now)
          controls.target.set(x, z + 6, -y)
          camera.position.set(x + 22, z + 26, -y + 38)
        }
        const key = `${sel}|${chosen.path.length}|${sh.name}`
        if (key !== routeKey || chosen.path !== routeOf) {
          routeKey = key
          routeOf = chosen.path
          const pts = chosen.path.flatMap((s) => [new THREE.Vector3(s.p0[0], s.p0[2], -s.p0[1]), new THREE.Vector3(s.p1[0], s.p1[2], -s.p1[1])])
          route.geometry.dispose()
          route.geometry = new THREE.BufferGeometry().setFromPoints(pts)
        }
      }

      // real drones: a ring on the floor, a pole up to the height they report and a tag with the end of the address
      const here = real.filter((d) => d.fix && isAlive(d))
      for (const d of here) {
        let m = markers.get(d.ip)
        if (!m) {
          const group = new THREE.Group()
          const ringMesh = new THREE.Mesh(new THREE.RingGeometry(13, 16, 40), new THREE.MeshBasicMaterial({ color: 0x0b7285, side: THREE.DoubleSide }))
          ringMesh.rotation.x = -Math.PI / 2
          ringMesh.position.y = 0.8
          const dot = new THREE.Mesh(new THREE.SphereGeometry(4, 16, 12), new THREE.MeshBasicMaterial({ color: 0x0b7285 }))
          const pole = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0x0b7285 }))
          const tag = new THREE.Sprite(new THREE.SpriteMaterial({ transparent: true, depthTest: false }))
          tag.scale.set(26, 13, 1)
          tag.renderOrder = 11
          group.add(ringMesh, dot, pole, tag)
          scene.add(group)
          m = { group, dot, pole, tag, key: '' }
          markers.set(d.ip, m)
        }
        m.group.position.set(d.x, 0, -d.y)
        const h = Math.max(d.z, 0)
        m.dot.position.y = h
        m.pole.geometry.dispose()
        m.pole.geometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, h, 0)])
        m.tag.position.y = h + 14
        const level = batteryLevel(d.batteryV)
        const key = `${d.ip}|${level}|${th}`
        if (key !== m.key) {
          m.key = key
          const mat = m.tag.material as THREE.SpriteMaterial
          mat.map?.dispose()
          mat.map = tagTexture(`…${d.ip.split('.').pop()}${level !== 'ok' ? ' ▲' : ''}`, c.accent, c.ink, c.sheet)
          mat.needsUpdate = true
        }
        for (const o of [m.dot, m.pole]) (o.material as THREE.Material & { color: THREE.Color }).color.set(c.accent)
      }
      for (const [ip, m] of markers) {
        if (!here.some((d) => d.ip === ip)) {
          scene.remove(m.group)
          markers.delete(ip)
        }
      }

      controls.update()
      renderer.render(scene, camera)
    }
    frame()

    api.current = {
      resize: (w, h) => {
        renderer.setSize(w, h)
        camera.aspect = w / Math.max(h, 1)
        camera.updateProjectionMatrix()
      },
      refit,
    }
    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      renderer.domElement.removeEventListener('pointerdown', onDown, { capture: true })
      renderer.domElement.removeEventListener('pointermove', onMoveEvent)
      renderer.domElement.removeEventListener('pointerup', onUp)
      controls.dispose()
      renderer.dispose()
      el.removeChild(renderer.domElement)
      api.current = null
    }
  }, [])

  useEffect(() => {
    if (size.width > 0 && size.height > 0) api.current?.resize(size.width, size.height)
  }, [size.width, size.height])

  return (
    <div className="mat3d" ref={host} style={{ width: size.width, height: size.height }}>
      {modelState !== 'ready' && <p className="model-status" role="status">{modelState === 'loading' ? tr('Загрузка 3D-сцены…') : tr('Не удалось загрузить модель. Переключитесь в 2D.')}</p>}
      <p className="mat3d-hint">{tr('Тяните, чтобы повернуть · колесо — масштаб · правая кнопка — сдвиг')}</p>
    </div>
  )
}
