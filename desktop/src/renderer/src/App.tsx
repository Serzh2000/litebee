import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { checkShow, DEFAULT_MAX_HEIGHT_CM, HARD_MAX_HEIGHT_CM, type Finding } from '@core/checks'
import { detectArea, FULL, migrateCells, QUARTERS, sameArea, type Area } from '@core/area'
import { groupFindings } from '@core/groups'
import { linesAt } from '@core/now'
import { AreaBar } from './components/AreaBar'
import { newProject, newSource, projectFileName } from '@core/project'
import { buildShow, type Show, type ShowData } from '@core/show'
import { CodePane } from './components/CodePane'
import type { CodeEditorHandle } from './components/CodeEditor'
import { CueSheet } from './components/CueSheet'
import { FleetRail } from './components/FleetRail'
import { DroneWindows } from './components/DroneWindows'
import { LivePanel } from './components/LivePanel'
import { NewProjectWizard } from './components/NewProjectWizard'
import { StartScreen } from './components/StartScreen'
import { localizeSource } from './lib/localize'
import { forget, remember } from './lib/recent'
import { useLang } from './state/useLang'
import { MatChart } from './components/MatChart'
import { MAX_DRONES } from '@core/project'
import { addDrone, freeStartCell, setStartCell, type Edit } from '@core/placement'
import { autoRoles, startCell } from '@core/roles'
import { useLink } from './state/useLink'
import { compileDrone, UploadUnsupported } from '@core/mission'
import { Readout } from './components/Readout'
import { Reference } from './components/Reference'
import { Checks } from './components/SidePanel'
import { TopBar } from './components/TopBar'
import { Transport } from './components/Transport'
import { SHOWS } from './data/shows'
import { baseName, openProjectFile, saveProjectFile } from './lib/files'
import { runner } from './python/runShow'
import { preflight } from './state/preflight'
import { usePlayback } from './state/usePlayback'
import { useSize } from './state/useSize'
import './App.css'
import { tr } from '@core/i18n'

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
}

function ownLimit(show: Show): number {
  const peak = Math.max(0, ...show.drones.flatMap((d) => d.path.flatMap((s) => [s.p0[2], s.p1[2]])))
  return peak > DEFAULT_MAX_HEIGHT_CM ? Math.min(Math.ceil(peak / 10) * 10, HARD_MAX_HEIGHT_CM) : DEFAULT_MAX_HEIGHT_CM
}

const LEVEL = { error: 'error', warn: 'warning', info: 'info' } as const

function Workspace({ project, actions, onSource, note, first }: WorkspaceProps) {
  const show = useMemo(() => buildShow(project.data), [project.data])
  const playback = usePlayback(show.duration, first ? START.t : 0)
  const [selected, setSelected] = useState<number | null>(first ? START.select : null)
  const [hoverCell, setHoverCell] = useState<number | null>(null)
  const [hint, setHint] = useState<string | null>(null)
  // Beside the map the code of each drone floats in a window of its own while the count sheet is used.
  const [windowsOn, setWindowsOn] = useState(true)
  // a drone that waits for a click on the map to be put on the cell
  const [placing, setPlacing] = useState<number | null>(null)
  const [closedWindows, setClosedWindows] = useState<Set<number>>(new Set())
  const [mode, setMode] = useState<Mode>(first ? START.mode : 'code')
  const [side, setSide] = useState<'checks' | 'ref'>(first ? START.side : 'checks')
  // A show that was made to fly as it is (an imported one) opens with a limit that is its own highest point.
  const [maxHeight, setMaxHeight] = useState(() => ownLimit(show))
  const [report, setReport] = useState<Report | null>(null)
  const [notice, setNotice] = useState('')
  const link = useLink()
  const [matRef, mat] = useSize<HTMLDivElement>()
  const editor = useRef<CodeEditorHandle | null>(null)
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
            ? tr('Номера клеток в коде записаны не числами (переменные, списки): перенести их автоматически нельзя. Впишите клетки числами или поправьте вручную.')
            : tr('В коде нет номеров клеток, которые можно сдвинуть.'),
        )
        return
      }
      if (editor.current) editor.current.replace(moved.source)
      else onSource(moved.source)
      chooseArea(to)
      setNotice(
        tr('Шоу перенесено: {n} клеток сдвинуты', { n: moved.changed }) + (moved.skipped ? tr(', {n} аргументов не числа, проверьте их вручную', { n: moved.skipped }) : '') + '.',
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
    if (mode === 'code') runner.warm()
  }, [mode])

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
    if (assigned.length === 0) return 'Справа выберите, каким дроном шоу будет каждый дрон на связи'
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
    setNotice(done === assigned.length ? tr('Миссия загружена в дронов: {n}.', { n: done }) : tr('Загружено {a} из {b}: смотрите причины в списке дронов.', { a: done, b: assigned.length }))
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

  const { steps, reason, cta } = preflight({ check, errors, connected: link.connected, loadBlock, loading, loaded, armed, flying })

  // Underlines in the code: the error of the run first, then one per finding that points at a line.
  const marks = useMemo(() => {
    const out: { line: number; level: 'error' | 'warning' | 'info'; message: string }[] = []
    if (project.run.state === 'error' && project.run.line) out.push({ line: project.run.line, level: 'error', message: tr(project.run.error ?? '') })
    for (const f of report?.findings ?? []) {
      if (f.line && f.level !== 'info') out.push({ line: f.line, level: LEVEL[f.level], message: tr(f.message) })
    }
    return out
  }, [project.run, report])

  const jump = (f: Finding) => {
    if (f.drone !== null) setSelected(f.drone)
    if (f.t !== null) playback.seek(f.t)
    if (f.line && mode === 'code') editor.current?.reveal(f.line)
  }

  const stepCount = show.drones.reduce((n, d) => n + d.steps.length, 0)
  // Which lines of the code are in effect at the time on the count sheet: the editor lights them.
  const now = useMemo(() => linesAt(show, playback.t, selected), [show, playback.t, selected])

  return (
    <div className="app">
      <TopBar
        project={project}
        actions={actions}
        steps={steps}
        reason={reason}
        cta={cta}
        onCheck={runCheck}
        mode={mode}
        onMode={setMode}
        link={link}
        onStep={onStep}
        onEmergency={emergency}
      />
      <div className="body" data-mode={mode}>
        {mode === 'code' ? (
          <CodePane
            project={project}
            marks={marks}
            steps={stepCount}
            editor={editor}
            onSource={onSource}
            onGoto={(line) => editor.current?.reveal(line)}
            now={now}
            t={playback.t}
            selected={selected}
            onSelect={setSelected}
            show={show}
            onSimulate={() => setMode('map')}
            onAddDrone={show.drones.length < MAX_DRONES ? addOne : null}
          />
        ) : (
          <FleetRail show={show} t={playback.t} selected={selected} onSelect={setSelected} onAdd={addOne} />
        )}
        <main className="field">
          <AreaBar area={area} onArea={chooseArea} from={fromArea} onMigrate={migrate} maxHeight={maxHeight} onMaxHeight={setMaxHeight} placing={placing !== null} onPlace={togglePlace} />
          {mode === 'map' && windowsOn && (playback.playing || playback.t > 0) && (
            <DroneWindows
              show={show}
              t={playback.t}
              source={project.source}
              selected={selected}
              onPick={(n) => setSelected((s) => (s === n ? null : n))}
              hidden={closedWindows}
              onHide={(n) => setClosedWindows((s) => new Set(s).add(n))}
            />
          )}
          <div className="mat-box" ref={matRef}>
            <MatChart
              area={area}
              show={show}
              t={playback.t}
              selected={selected}
              onSelect={setSelected}
              live={link.drones}
              hoverCell={hoverCell}
              onHoverCell={setHoverCell}
              onPick={placing !== null ? placeAt : undefined}
              onMove={standOn}
              size={{ width: Math.max(mat.width - 28, 0), height: Math.max(mat.height - 10, 0) }}
            />
          </div>
        </main>
        <aside className="side">
          <Readout
            show={show}
            t={playback.t}
            selected={selected}
            hoverCell={hoverCell}
            compact={mode === 'code'}
            start={selected === null ? null : startCell(show.drones.find((d) => d.number === selected)?.steps ?? [])}
            placing={placing !== null}
            onPlace={togglePlace}
          />
          <LivePanel
            active={link.active}
            archive={link.archive}
            numbers={show.drones.map((d) => d.number)}
            roles={roles}
            onRole={(ip, n) => setManual((r) => ({ ...r, [ip]: n }))}
            autoIps={new Set(Object.keys(roles).filter((ip) => roles[ip] && !(ip in manual)))}
            onForget={() => void link.forget()}
            uploads={uploads}
          />
          <div className="tabs" role="tablist" aria-label={tr('Боковая панель')}>
            <button type="button" role="tab" aria-selected={side === 'checks'} onClick={() => setSide('checks')}>
              {tr('Проверки')}
            </button>
            <button type="button" role="tab" aria-selected={side === 'ref'} onClick={() => setSide('ref')}>
              {tr('Справочник')}
            </button>
          </div>
          {side === 'checks' ? (
            <Checks groups={groups} stale={check === 'stale'} onJump={jump} />
          ) : (
            <Reference onInsert={(code) => editor.current?.insert(code)} />
          )}
          <p className="notice" role="status" aria-live="assertive">
            {tr(notice || note)}
          </p>
        </aside>
        {mode === 'map' && (
        <div className="dock">
            <Transport
              t={playback.t}
              duration={show.duration}
              playing={playback.playing}
              speed={playback.speed}
              onToggle={playback.toggle}
              onSpeed={playback.setSpeed}
              onSeek={playback.seek}
            />
          </div>
        )}
        {mode === 'map' && (
          <div className="drawer">
            <p className="drawer-hint">
              <span>{hint ?? tr('Тяните по партитуре или ← → (Shift: по 10 с), ↑ ↓ выбирают дрон')}</span>
              {mode === 'map' && (
                <button
                  type="button"
                  className="drawer-toggle"
                  aria-pressed={windowsOn}
                  onClick={() => {
                    setWindowsOn((on) => !on)
                    setClosedWindows(new Set())
                  }}
                >
                  {windowsOn ? tr('Окна кода: вкл') : tr('Окна кода: выкл')}
                </button>
              )}
            </p>
            <CueSheet
              show={show}
              t={playback.t}
              selected={selected}
              onSelect={setSelected}
              onSeek={playback.seek}
              onHover={setHint}
              height={240}
            />
          </div>
        )}
      </div>
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
  const [wizard, setWizard] = useState(false)
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
          return 'ok' in result
            ? { ...p, data: result.ok, run: { state: 'ok' } }
            : { ...p, run: { state: 'error', error: result.error, line: result.line } }
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
    />
      {home && (
        <StartScreen
          onWizard={() => setWizard(true)}
          onOpen={actions.onOpen}
          onOpenRecent={actions.onOpenPath}
          onExample={actions.onExample}
          onContinue={() => setHome(false)}
          projectName={project.data.name}
        />
      )}
      {wizard && (
        <NewProjectWizard
          onCancel={() => setWizard(false)}
          onBlank={(n, c) => (setWizard(false), actions.onNew(n, c))}
          onExample={(id) => (setWizard(false), actions.onExample(id))}
        />
      )}
    </>
  )
}
