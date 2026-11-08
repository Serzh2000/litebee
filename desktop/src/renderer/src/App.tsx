import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { checkShow, DEFAULT_MAX_HEIGHT_CM, HARD_MAX_HEIGHT_CM, type Finding } from '@core/checks'
import { detectArea, FULL, migrateCells, QUARTERS, sameArea, type Area } from '@core/area'
import { groupFindings } from '@core/groups'
import { linesAt } from '@core/now'
import { AreaBar } from './components/AreaBar'
import { newProject, newSource, projectFileName } from '@core/project'
import { buildShow, type Show, type ShowData } from '@core/show'
import { DroneEditor } from './components/DroneEditor'
import type { CodeEditorHandle } from './components/CodeEditor'
import { NewProjectWizard } from './components/NewProjectWizard'
import { StartScreen } from './components/StartScreen'
import { localizeSource } from './lib/localize'
import { forget, remember } from './lib/recent'
import { useLang } from './state/useLang'
import { lazy, Suspense } from 'react'
import { fitMap, MatChart } from './components/MatChart'

const Mat3D = lazy(() => import('./components/Mat3D').then((m) => ({ default: m.Mat3D })))
import { MAX_DRONES } from '@core/project'
import { sectionAt, splitDrones } from '@core/sections'
import { addDrone, freeStartCell, setStartCell, type Edit } from '@core/placement'
import { autoRoles, startCell } from '@core/roles'
import { batteryLevel, fmtVolts, useLink } from './state/useLink'
import { compileDrone, unprovenSteps, UploadUnsupported } from '@core/mission'
import { Inspector } from './components/Inspector'
import { Sidebar } from './components/Sidebar'
import { RightPanel, type Tab } from './components/RightPanel'
import { Reference } from './components/Reference'
import { Checks } from './components/SidePanel'
import { Timetable } from './components/Timetable'
import { LivePanel } from './components/LivePanel'
import { Transport } from './components/Transport'
import { TopBar } from './components/TopBar'
import { tail } from './components/LivePanel'
import { SHOWS } from './data/shows'
import { baseName, openProjectFile, saveProjectFile } from './lib/files'
import { runner } from './python/runShow'
import { honestyNotes, preflight } from './state/preflight'
import { usePlayback } from './state/usePlayback'
import { useSize } from './state/useSize'
import './App.css'
import './styles/studio.css'
import { tr } from '@core/i18n'

/** The tool strip is one row pinned 16 px inside the well's top-left corner: 16 above, 28 of controls. */
const STRIP_H = 48
/** The most the strip can be wide (px, 16 from the left edge included): a map whose grid starts to the right of it needs no row of its own. */
const STRIP_W = 372

interface Report {
  findings: Finding[]
  limit: number
}

/** Start state from the address (?show=my_dream&select=4&t=30&mode=map): a deep link, and how screenshots reach a state. */
const PARAMS = new URLSearchParams(window.location.search)
const START = {
  show: PARAMS.get('show'),
  select: PARAMS.get('select') ? Number(PARAMS.get('select')) : null,
  t: PARAMS.get('t') ? Number(PARAMS.get('t')) : 0,
  mode: PARAMS.get('mode') === 'map' ? ('map' as const) : ('code' as const),
  side: PARAMS.get('side') === 'ref' ? ('ref' as const) : ('checks' as const),
}

export type Mode = 'code' | 'map'

/** The last run of the source: running, fine, or failed with a message and the line it points at. */
export interface RunState {
  state: 'running' | 'ok' | 'error'
  error?: string
  line?: number | null
}

/**
 * The open project is a Python show: the source is the truth, `data` is what its last good run made of it (the map
 * and the count sheet are drawn from `data`), `path` is where the file lives (null until saved).
 */
export interface Project {
  key: number
  source: string
  data: ShowData
  /** the file name shown while there is no path: the example's file or a new project's name */
  label: string
  path: string | null
  saved: boolean
  run: RunState
}

export interface ProjectActions {
  onNew: (name: string, drones: number) => void
  onOpen: () => void
  onSave: (asNew: boolean) => void
  onExample: (id: string) => void
  /** the wizard of a new project */
  onWizard: () => void
  /** the start window */
  onHome: () => void
  onOpenPath: (path: string) => void
}

interface WorkspaceProps {
  project: Project
  actions: ProjectActions
  onSource: (text: string) => void
  note: string
  first: boolean
  inactive: boolean
}

function ownLimit(show: Show): number {
  const peak = Math.max(0, ...show.drones.flatMap((d) => d.path.flatMap((s) => [s.p0[2], s.p1[2]])))
  return peak > DEFAULT_MAX_HEIGHT_CM ? Math.min(Math.ceil(peak / 10) * 10, HARD_MAX_HEIGHT_CM) : DEFAULT_MAX_HEIGHT_CM
}

const LEVEL = { error: 'error', warn: 'warning', info: 'info' } as const

function Workspace({ project, actions, onSource, note, first, inactive }: WorkspaceProps) {
  const show = useMemo(() => buildShow(project.data), [project.data])
  const playback = usePlayback(show.duration, first ? START.t : 0)
  const [selected, setSelected] = useState<number | null>(first ? START.select : null)
  const [hoverCell, setHoverCell] = useState<number | null>(null)
  const [mapTags, setMapTags] = useState(false)
  const [mapRoutes, setMapRoutes] = useState(true)
  const [hint, setHint] = useState<string | null>(null)
  // a drone that waits for a click on the map to be put on the cell
  const [view, setViewState] = useState<'2d' | '3d'>(() => {
    try {
      return (PARAMS.get('view') ?? localStorage.getItem('litebee.view')) === '3d' ? '3d' : '2d'
    } catch {
      return '2d'
    }
  })
  const setView = (v: '2d' | '3d') => {
    setViewState(v)
    try {
      localStorage.setItem('litebee.view', v)
    } catch {
      /* the choice is simply not remembered */
    }
  }
  const [placing, setPlacing] = useState<number | null>(null)
  const [mode, setMode] = useState<Mode>('map')
  const [inspectorOpen, setInspectorOpen] = useState(() => window.innerWidth >= 1100)
  // A show that was made to fly as it is (an imported one) opens with a limit that is its own highest point.
  const [maxHeight, setMaxHeight] = useState(() => ownLimit(show))
  const [report, setReport] = useState<Report | null>(null)
  const [notice, setNotice] = useState('')
  const link = useLink()
  const [matRef, mat] = useSize<HTMLDivElement>()
  const [tab, setTab] = useState<Tab>(() => {
    const asked = PARAMS.get('tab') ?? (START.side === 'ref' ? 'ref' : null)
    if (first && (asked === 'score' || asked === 'code' || asked === 'fleet' || asked === 'checks' || asked === 'ref')) return asked
    return first && START.select !== null ? 'code' : 'score'
  })
  const editor = useRef<CodeEditorHandle | null>(null)
  const [gotoLine, setGotoLine] = useState<number | null>(null)
  // The working area follows the show until the person picks one: a show written for a quarter opens on that quarter.
  const [area, setArea] = useState<Area>(() => detectArea(project.data))
  const areaChosen = useRef(false)
  useEffect(() => {
    if (areaChosen.current || show.drones.length === 0) return
    areaChosen.current = true
    setArea(detectArea(project.data))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [show])
  const chooseArea = (a: Area) => {
    areaChosen.current = true
    setArea(a)
  }

  const runCheck = useCallback(() => {
    setReport({ findings: checkShow(show, { maxHeightCm: maxHeight, area }), limit: maxHeight })
  }, [show, maxHeight, area])

  // Every new run of the source is checked again, so the list and the underlines follow what is typed.
  useEffect(() => {
    runCheck()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [show, area])

  // The quarter the show is written for: the chosen area when it is a quarter, else the quarter its cells fit in.
  const fromArea = useMemo(() => {
    const own = QUARTERS.find((q) => sameArea(q.area, area))?.area
    if (own) return own
    const found = detectArea(project.data)
    return sameArea(found, FULL) ? null : found
  }, [area, project.data])

  const migrate = (to: Area) => {
    if (!fromArea) {
      setNotice(tr('Шоу занимает больше одной четверти: переносить некуда. Выберите четверть, в которой оно написано.'))
      return
    }
    try {
      const moved = migrateCells(project.source, to.col0 - fromArea.col0, to.row0 - fromArea.row0)
      if (moved.changed === 0) {
        setNotice(
          moved.skipped
            ? tr(
                'Номера клеток в коде записаны не числами (переменные, списки): перенести их автоматически нельзя. Впишите клетки числами или поправьте вручную.',
              )
            : tr('В коде нет номеров клеток, которые можно сдвинуть.'),
        )
        return
      }
      if (editor.current) editor.current.replace(moved.source)
      else onSource(moved.source)
      chooseArea(to)
      setNotice(
        tr('Шоу перенесено: {n} клеток сдвинуты', { n: moved.changed }) +
          (moved.skipped ? tr(', {n} аргументов не числа, проверьте их вручную', { n: moved.skipped }) : '') +
          '.',
      )
    } catch (e) {
      setNotice(e instanceof Error ? tr(e.message) : tr('Не удалось перенести шоу.'))
    }
  }

  /** A change of the code made by the app (a drone added, a drone moved): it goes through the editor, so Ctrl+Z takes it back. */
  const apply = (edit: Edit): boolean => {
    if (edit.error) {
      setNotice(tr(edit.error))
      return false
    }
    if (editor.current) editor.current.replace(edit.source)
    else onSource(edit.source)
    return true
  }

  const addOne = () => {
    const number = Math.max(0, ...show.drones.map((d) => d.number)) + 1
    const cell = freeStartCell(show, area)
    if (!apply(addDrone(project.source, show, area))) return
    setSelected(number)
    setNotice(tr('Дрон {n} добавлен на клетку {c}. Поставьте его туда на коврике.', { n: number, c: cell }))
  }

  const placeAt = (cell: number) => {
    if (placing === null) return
    const number = placing
    setPlacing(null)
    standOn(number, cell)
  }

  const togglePlace = () => {
    if (placing !== null) {
      setPlacing(null)
      setNotice('')
    } else if (selected === null) {
      setNotice(tr('Сначала выберите дрона: нажмите его фишку или самого дрона на карте.'))
    } else {
      setPlacing(selected)
      setNotice(tr('Нажмите клетку на карте, куда поставить дрон {n}. Esc отменяет.', { n: selected }))
    }
  }

  const standOn = (number: number, cell: number) => {
    setSelected(number)
    if (apply(setStartCell(project.source, number, cell))) setNotice(tr('Дрон {n} теперь стартует с клетки {c}.', { n: number, c: cell }))
  }

  useEffect(() => {
    runner.warm()
  }, [])

  const emergency = useCallback(() => {
    playback.stop()
    setPlacing(null)
    if (!link.connected) {
      setNotice(tr('Аварийная посадка: дронов на связи нет, остановлена симуляция.'))
      return
    }
    void link.emergency().then((n) => setNotice(tr('Аварийная посадка: команда отправлена дронам: {n}.', { n })))
  }, [playback, link])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') return emergency()
      if (!e.ctrlKey && !e.metaKey) return
      const k = e.key.toLowerCase()
      if (k === 's') actions.onSave(e.shiftKey)
      else if (k === 'o') actions.onOpen()
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [emergency, actions])

  const groups = useMemo(() => (report ? groupFindings(report.findings, report.limit) : null), [report])
  const errors = groups?.filter((g) => g.level === 'error').length ?? 0
  const check = !report ? null : report.limit !== maxHeight ? 'stale' : errors > 0 ? 'errors' : 'ok'
  // Which drone of the show each drone on the link is. The person chooses; nothing is uploaded to a drone without a role.
  // What the person picked wins; a drone they left alone gets its number from the cell it stands on.
  const [manual, setManual] = useState<Record<string, number | null>>({})
  const auto = useMemo(() => autoRoles(show, link.active), [show, link.active])
  const roles = useMemo(() => {
    const taken = new Set(Object.values(manual).filter((n): n is number => n !== null))
    const out: Record<string, number | null> = {}
    for (const d of link.active) {
      out[d.ip] = d.ip in manual ? manual[d.ip] : auto[d.ip] && !taken.has(auto[d.ip]) ? auto[d.ip] : null
    }
    return out
  }, [manual, auto, link.active])
  const [uploads, setUploads] = useState<Record<string, { ok: boolean; message: string }>>({})
  const [loading, setLoading] = useState(false)
  // A changed show or limit makes what is on board out of date.
  useEffect(() => setUploads({}), [show, maxHeight])
  const assigned = link.active.filter((d) => roles[d.ip])
  const loadBlock = useMemo(() => {
    if (!link.connected) return 'Нет дронов на связи'
    if (assigned.length === 0) return 'Назначьте бортам дроны на связи в расписании'
    for (const d of assigned) {
      const model = show.drones.find((m) => m.number === roles[d.ip])
      if (!model) return `В шоу нет дрона ${roles[d.ip]}`
      try {
        compileDrone(model.steps)
      } catch (e) {
        if (e instanceof UploadUnsupported) return `Дрон ${model.number}: ${e.message}`
        throw e
      }
    }
    return null
  }, [link.connected, assigned, roles, show])
  const onBoard = new Set(link.state?.loaded ?? [])
  const loaded = assigned.length > 0 && assigned.every((d) => uploads[d.ip]?.ok && onBoard.has(d.ip))
  const armed = Boolean(link.state?.armed)
  const flying = Boolean(link.state?.flying)

  const load = async () => {
    if (loadBlock || loading || !window.litebee) return
    setLoading(true)
    setNotice('')
    let done = 0
    for (const d of assigned) {
      const model = show.drones.find((m) => m.number === roles[d.ip])!
      const r = await window.litebee.link.upload({ ip: d.ip, steps: model.steps, maxHeightCm: maxHeight })
      setUploads((u) => ({ ...u, [d.ip]: r }))
      if (r.ok) done++
    }
    link.refresh()
    setLoading(false)
    setNotice(
      done === assigned.length
        ? tr('Миссия загружена в дронов: {n}.', { n: done })
        : tr('Загружено {a} из {b}: смотрите причины в списке дронов.', { a: done, b: assigned.length }),
    )
  }

  const arm = async () => {
    await link.arm(!armed)
    setNotice(armed ? tr('Взвод снят.') : tr('Дроны взведены. Старт спросит подтверждение.'))
  }

  const go = async () => {
    const ips = assigned.map((d) => d.ip)
    const r = await link.go(ips, maxHeight)
    if (r) setNotice(tr(r.message))
  }

  const onStep = (i: number) => {
    if (i === 1) void load()
    else if (i === 2) void arm()
    else if (i === 3) void go()
  }

  // A drone whose steps cannot be compiled yet (code_z and the like) counts as unproven too.
  const unproven = useMemo(
    () =>
      show.drones.filter((d) => {
        try {
          return unprovenSteps(compileDrone(d.steps)).length > 0
        } catch {
          return true
        }
      }).length,
    [show],
  )
  const notes = honestyNotes(show.drones.length, unproven)
  const { steps, reason } = preflight({ check, errors, connected: link.connected, loadBlock, loading, loaded, armed, flying })

  // Underlines in the code: the error of the run first, then one per finding that points at a line.
  const marks = useMemo(() => {
    const out: { line: number; level: 'error' | 'warning' | 'info'; message: string }[] = []
    if (project.run.state === 'error' && project.run.line) out.push({ line: project.run.line, level: 'error', message: tr(project.run.error ?? '') })
    for (const f of report?.findings ?? []) {
      if (f.line && f.level !== 'info') out.push({ line: f.line, level: LEVEL[f.level], message: tr(f.message) })
    }
    return out
  }, [project.run, report])

  /** a drone picked on the scene opens its program in the right window */
  const pickOnMap = (n: number | null) => {
    setSelected(n)
    if (n !== null) setTab('code')
  }

  const jump = (f: Finding) => {
    if (f.drone !== null) setSelected(f.drone)
    if (f.t !== null) playback.seek(f.t)
    if (f.line) {
      // the code of the drone that owns the line opens and the cursor goes to it
      const split = splitDrones(project.source)
      const owner = split ? sectionAt(split, f.line) : null
      if (owner) setSelected(owner.number)
      setGotoLine(f.line)
      setTab('code')
    }
  }

  // Which lines of the code are in effect at the time on the timetable: the editor lights them.
  const now = useMemo(() => linesAt(show, playback.t, selected), [show, playback.t, selected])

  // The person's choice of the drone on the link that flies drone `number`: whoever had that number gives it up.
  const assign = (number: number, ip: string | null) =>
    setManual((m) => {
      const next = { ...m }
      for (const d of link.active) if (roles[d.ip] === number) next[d.ip] = null
      if (ip) next[ip] = number
      return next
    })

  // The one finding of the screen, read first under the title: what most needs attention before a flight.
  const weak = link.active
    .map((d) => ({ d, level: batteryLevel(d.batteryV) }))
    .filter((x) => x.level !== 'ok')
    .sort((a, b) => (a.level === b.level ? a.d.batteryV - b.d.batteryV : a.level === 'low' ? -1 : 1))[0]
  const finding: { tone: 'warning' | 'negative' | 'info' | 'next'; text: string } =
    check === 'errors'
      ? { tone: 'negative', text: tr(reason) }
      : weak
        ? {
            tone: weak.level === 'low' ? 'negative' : 'warning',
            text: tr(weak.level === 'low' ? 'Дрон {ip}: батарея {v}, взлёт запрещён' : 'Дрон {ip}: батарея {v}, лучше заменить', {
              ip: tail(weak.d.ip),
              v: fmtVolts(weak.d.batteryV),
            }),
          }
        : notes[0]
          ? { tone: 'info', text: tr(notes[0]) }
          : { tone: 'next', text: tr(reason) }

  // The map takes the well. The tools are a row over its top-left corner: when the map is centred and its grid starts to
  // the right of them (a wide well) it has the whole height, otherwise it sits under the row.
  const full = fitMap(area, mat.width, mat.height)
  const stripHeight = mat.width < 430 ? 88 : STRIP_H
  const clear = (mat.width - full.gridW) / 2 >= STRIP_W + 16
  const mapSize = clear ? { width: mat.width, height: mat.height } : { width: mat.width, height: Math.max(mat.height - stripHeight, 0) }
  const matPad = clear ? undefined : { paddingTop: stripHeight }

  const well = (
    <div className="well">
      <AreaBar
        area={area}
        onArea={chooseArea}
        from={fromArea}
        onMigrate={migrate}
        maxHeight={maxHeight}
        onMaxHeight={setMaxHeight}
        view={view}
        onView={setView}
        tags={mapTags}
        onTags={() => setMapTags((value) => !value)}
        routes={mapRoutes}
        onRoutes={() => setMapRoutes((value) => !value)}
      />
      {selected !== null && view === '2d' && placing === null && (
        <p className="well-hint">{tr('Перетащите дрона на другую клетку')}</p>
      )}
      <div className="mat-box" ref={matRef} style={matPad}>
        {view === '3d' ? (
          <Suspense fallback={<div className="scene-loading" role="status">{tr('Загрузка 3D-сцены…')}</div>}>
            <Mat3D show={show} t={playback.t} selected={selected} onSelect={pickOnMap} area={area} live={link.drones} onMove={standOn} size={mapSize} />
          </Suspense>
        ) : (
          <MatChart
            area={area}
            show={show}
            t={playback.t}
            selected={selected}
            onSelect={pickOnMap}
            live={link.drones}
            hoverCell={hoverCell}
            onHoverCell={setHoverCell}
            onPick={placing !== null ? placeAt : undefined}
            onMove={standOn}
            size={mapSize}
            showTags={mapTags}
            showRoutes={mapRoutes}
          />
        )}
      </div>
      {view === '2d' && <div className="map-caption" aria-hidden="true"><span>{tr('Клетка: 40 × 40 см')}</span><span>{area.cols * 40} × {area.rows * 40} {tr('см')}</span></div>}
    </div>
  )

  const inspector = (
    <Inspector
      show={show}
      t={playback.t}
      selected={selected}
      hoverCell={hoverCell}
      start={selected === null ? null : startCell(show.drones.find((d) => d.number === selected)?.steps ?? [])}
      placing={placing !== null}
      onPlace={togglePlace}
      notice={tr(notice || note)}
      editor={
        selected === null ? null : (
          <DroneEditor
            project={project}
            drone={selected}
            marks={marks}
            editor={editor}
            onSource={onSource}
            now={now}
            goto={gotoLine}
            onGotoDone={() => setGotoLine(null)}
          />
        )
      }
    />
  )



  return (
    <div className="app" data-mode={mode} data-inspector={inspectorOpen} inert={inactive}>
      <Sidebar project={project} actions={actions} mode={mode} onMode={setMode} reference={tab === 'ref' && inspectorOpen} onReference={() => { setTab('ref'); setInspectorOpen(true) }} link={link} />
      <TopBar
        mode={mode}
        project={project}
        actions={actions}
        steps={steps}
        onCheck={runCheck}
        onStep={onStep}
        onEmergency={emergency}
        status={flying ? 'flying' : armed ? 'armed' : 'sim'}
        finding={hint ? { tone: 'info', text: hint } : finding}
        onSave={() => actions.onSave(false)}
        inspectorOpen={inspectorOpen}
        onInspector={() => setInspectorOpen((open) => !open)}
      />
      <main className="sheet">
        <div className="stage">
          <div className="work">{well}</div>
          {inspectorOpen && (
            <RightPanel
              tab={tab}
              onTab={setTab}
              fleetCount={link.active.length}
              transport={
                <Transport
                  t={playback.t}
                  duration={show.duration}
                  playing={playback.playing}
                  speed={playback.speed}
                  onToggle={playback.toggle}
                  onSpeed={playback.setSpeed}
                  onSeek={playback.seek}
                />
              }
              score={
                <Timetable
                  show={show}
                  t={playback.t}
                  selected={selected}
                  onSelect={setSelected}
                  onSeek={playback.seek}
                  onHover={setHint}
                  onAdd={show.drones.length < MAX_DRONES ? addOne : null}
                />
              }
              code={inspector}
              checks={<Checks groups={groups} stale={check === 'stale'} onJump={jump} />}
              reference={<Reference onInsert={(code) => editor.current?.insert(code)} />}
              fleet={
                link.active.length === 0 && link.archive.length === 0 ? (
                  <p className="rp-none">{tr('Включите дроны: они найдут компьютер сами.')}</p>
                ) : (
                  <div className="rp-fleet">
                    <LivePanel
                      active={link.active}
                      archive={link.archive}
                      numbers={show.drones.map((d) => d.number)}
                      roles={roles}
                      autoIps={new Set(Object.keys(roles).filter((ip) => roles[ip] && !(ip in manual)))}
                      onRole={(ip, n) => (n === null ? assign(roles[ip] ?? -1, null) : assign(n, ip))}
                      uploads={uploads}
                      onForget={() => void link.forget()}
                    />
                  </div>
                )
              }
            />
          )}
        </div>
      </main>
    </div>
  )
}

const EMPTY: ShowData = { name: '', drones: {} }

export default function App() {
  const firstShow = SHOWS.find((s) => s.id === START.show) ?? SHOWS.find((s) => s.id === 'my_dream') ?? SHOWS[0]
  const [project, setProject] = useState<Project>({
    key: 0,
    source: firstShow.source,
    data: firstShow.data ?? EMPTY,
    label: firstShow.file,
    path: null,
    saved: true,
    run: { state: 'ok' },
  })
  useLang() // the whole page redraws when the language changes
  // the start window greets a launch without an address that points at a show
  const [home, setHome] = useState(START.show === null)
  const [wizard, setWizard] = useState(PARAMS.get('wizard') === '1')
  const [wizardTab, setWizardTab] = useState<'example' | 'blank'>('example')
  const [opened, setOpened] = useState(0) // projects opened by the user; the start state only belongs to the first one
  const [note, setNote] = useState('')

  // The source runs in Python a moment after the last keystroke; a run that is overtaken by a newer one is dropped.
  const lastRun = useRef<string | null>(null)
  useEffect(() => {
    const { key, source } = project
    const token = `${key}:${source}`
    if (lastRun.current === token) return
    const first = lastRun.current === null
    const timer = setTimeout(
      async () => {
        lastRun.current = token
        setProject((p) => (p.key === key && p.source === source ? { ...p, run: { state: 'running' } } : p))
        const result = await runner.run(source, project.path ? baseName(project.path) : 'show.py')
        setProject((p) => {
          if (p.key !== key || p.source !== source) return p
          return 'ok' in result ? { ...p, data: result.ok, run: { state: 'ok' } } : { ...p, run: { state: 'error', error: result.error, line: result.line } }
        })
      },
      first ? 0 : 450,
    )
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.key, project.source])

  const replace = (source: string, data: ShowData, label: string, path: string | null, saved: boolean, message: string) => {
    lastRun.current = ''
    setProject((p) => ({ key: p.key + 1, source, data, label, path, saved, run: { state: 'running' } }))
    setOpened((n) => n + 1)
    setNote(message)
  }

  const actions: ProjectActions = {
    onNew: (name, drones) => {
      replace(localizeSource(newSource(name, drones)), newProject(name, drones), `${projectFileName(name || 'новый', 'py')}`, null, false, '')
      setHome(false)
    },
    onExample: (id) => {
      const s = SHOWS.find((x) => x.id === id)
      if (s) replace(localizeSource(s.source), s.data ?? EMPTY, s.file, null, true, '')
      setHome(false)
    },
    onOpen: async () => {
      try {
        const file = await openProjectFile()
        if (!file) return
          replace(file.text, EMPTY, baseName(file.path), file.path, true, '')
        if (window.litebee) remember(file.path, baseName(file.path))
        setHome(false)
      } catch (e) {
        setNote(e instanceof Error ? e.message : tr('Не удалось открыть файл.'))
      }
    },
    onOpenPath: async (path) => {
      const file = await window.litebee?.readProject(path)
      if (!file) {
        forget(path)
        setNote(tr('Файл не найден: {name}', { name: baseName(path) }))
        return
      }
      replace(file.text, EMPTY, baseName(file.path), file.path, true, '')
      remember(file.path, baseName(file.path))
      setHome(false)
    },
    onSave: async (asNew) => {
      try {
        const done = await saveProjectFile(project.source, asNew ? null : project.path, project.data.name || 'show')
        if (!done) return
        setProject((p) => ({ ...p, path: done.path, saved: true }))
        if (window.litebee) remember(done.path, baseName(done.path))
        setNote(tr('Сохранено: {name}', { name: baseName(done.path) }))
      } catch (e) {
        setNote(e instanceof Error ? tr('Не удалось сохранить: {why}', { why: e.message }) : tr('Не удалось сохранить файл.'))
      }
    },
    onWizard: () => setWizard(true),
    onHome: () => setHome(true),
  }

  return (
    <>
      <Workspace
        key={project.key}
        project={project}
        actions={actions}
        onSource={(text) => setProject((p) => ({ ...p, source: text, saved: false }))}
        note={note}
        first={opened === 0}
        inactive={home || wizard}
      />
      {home && (
        <StartScreen
          inactive={wizard}
          onWizard={(tab) => {
            setWizardTab(tab)
            setWizard(true)
          }}
          onOpen={actions.onOpen}
          onOpenRecent={actions.onOpenPath}
          onExample={actions.onExample}
          onContinue={() => setHome(false)}
          projectName={project.data.name}
        />
      )}
      {wizard && (
        <NewProjectWizard
          initialTab={wizardTab}
          onCancel={() => setWizard(false)}
          onBlank={(n, c) => (setWizard(false), actions.onNew(n, c))}
          onExample={(id) => (setWizard(false), actions.onExample(id))}
        />
      )}
    </>
  )
}
