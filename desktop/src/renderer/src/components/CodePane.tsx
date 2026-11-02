import { useEffect, useImperativeHandle, useMemo, useRef, useState, type Ref } from 'react'
import { CircleAlert, CircleCheck, FileText, LoaderCircle, Play, Plus } from 'lucide-react'
import { joinDrones, sectionAt, splitDrones } from '@core/sections'
import type { Show } from '@core/show'
import type { Project } from '../App'
import { baseName } from '../lib/files'
import { CodeEditor, type CodeEditorHandle } from './CodeEditor'
import './CodePane.css'
import { tr } from '@core/i18n'

interface Props {
  project: Project
  show: Show
  marks: { line: number; level: 'error' | 'warning' | 'info'; message: string }[]
  steps: number
  editor: Ref<CodeEditorHandle>
  onSource: (text: string) => void
  onGoto: (line: number) => void
  now: { run: number[]; light: number[] }
  /** show time in seconds and the selected drone, for the line under the header */
  t: number
  selected: number | null
  onSelect: (n: number | null) => void
  /** to the simulation tab, where the time can be played and scrubbed */
  onSimulate: () => void
  /** one more drone, put on a free cell */
  onAddDrone: (() => void) | null
}

type Tab = 'all' | number

/**
 * The code of the show with the state of its last run: what the map and the count sheet are drawn from. The code is
 * written whole or drone by drone (a tab for each `show.drone(N)` block); while the count sheet is used a window per
 * drone shows the line each of them runs now, so all drones stay in view whichever tab is open.
 */
export function CodePane({ project, show, marks, steps, editor, onSource, onGoto, now, t, selected, onSelect, onSimulate, onAddDrone }: Props) {
  const { run } = project
  const file = project.path ? baseName(project.path) : project.label

  const split = useMemo(() => splitDrones(project.source), [project.source])
  const [tab, setTab] = useState<Tab>('all')
  const section = tab === 'all' || !split ? null : (split.sections.find((s) => s.number === tab) ?? null)
  const inner = useRef<CodeEditorHandle | null>(null)
  const pending = useRef<number | null>(null)

  // A drone that disappeared from the code (renamed, deleted) takes its tab with it.
  useEffect(() => {
    if (tab !== 'all' && !section) setTab('all')
  }, [tab, section])
  // A new project starts on the whole code.
  useEffect(() => setTab('all'), [project.key])
  // Picking a drone on the map or on the count sheet brings its code, when the code is shown drone by drone.
  useEffect(() => {
    if (tab !== 'all' && selected !== null && split?.sections.some((s) => s.number === selected)) setTab(selected)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected])

  const value = section ? section.text : project.source
  const lineShift = section ? section.line - 1 : 0
  const inView = (line: number) => !section || (line >= section.line && line < section.line + section.lines)
  const tabMarks = useMemo(
    () => marks.filter((m) => inView(m.line)).map((m) => ({ ...m, line: m.line - lineShift })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [marks, section],
  )
  const tabNow = useMemo(
    () => ({ run: now.run.filter(inView).map((l) => l - lineShift), light: now.light.filter(inView).map((l) => l - lineShift) }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [now, section],
  )

  // The editor handle the rest of the app uses speaks in lines of the whole file; this maps it onto the open tab.
  useImperativeHandle(editor, () => ({
    reveal(line) {
      if (!section) return inner.current?.reveal(line)
      if (inView(line)) return inner.current?.reveal(line - lineShift)
      const other = split ? sectionAt(split, line) : null
      pending.current = line
      setTab(other ? other.number : 'all')
    },
    insert: (text) => inner.current?.insert(text),
    replace(text) {
      if (!section) return inner.current?.replace(text)
      setTab('all')
      onSource(text)
    },
  }))
  // A jump to a line of another drone waits until that drone's code is on the screen.
  useEffect(() => {
    const line = pending.current
    if (line === null) return
    pending.current = null
    const open = tab === 'all' ? null : split?.sections.find((s) => s.number === tab)
    inner.current?.reveal(open ? line - (open.line - 1) : line)
  }, [tab, split])

  const change = (text: string) => onSource(section && split ? joinDrones(split, section.number, text) : text)
  return (
    <section className="codepane" aria-label={tr('Код шоу')}>
      <div className="codebar">
        <h2 title={file}>{file}</h2>
        <button type="button" className="codepane-sim" onClick={onSimulate} title={tr('Открыть симуляцию: карта, партитура, воспроизведение')}>
          <Play size={13} strokeWidth={2} aria-hidden="true" />
          {tr('Смотреть')}
        </button>
        <span className="codepane-run" data-state={run.state} role="status" title={`${file}${project.saved ? '' : ' · ' + tr('изменён')}`}>
          {run.state === 'running' && <LoaderCircle size={14} strokeWidth={2} aria-label={tr('Запускаю')} />}
          {run.state === 'ok' && (
            <>
              <CircleCheck size={14} strokeWidth={2} aria-hidden="true" />
              {tr('{n} шагов', { n: steps })}
            </>
          )}
          {run.state === 'error' && (
            <>
              <CircleAlert size={14} strokeWidth={2} aria-hidden="true" /> {tr('Ошибка')}
            </>
          )}
          {!project.saved && <i className="codepane-dirty" title={tr('Есть несохранённые изменения')} />}
        </span>
      </div>
      <div className="codepane-body">
        {split && (
          <nav className="siderail" aria-label={tr('Код по дронам')}>
            <div className="siderail-inner" role="tablist" aria-orientation="vertical">
              <button type="button" role="tab" aria-selected={tab === 'all'} title={tr('Весь код')} onClick={() => setTab('all')}>
                <span className="sr-num">
                  <FileText size={15} strokeWidth={1.9} aria-hidden="true" />
                </span>
                <span className="sr-label">{tr('Весь код')}</span>
              </button>
              {split.sections.map((s) => (
                <button
                  key={s.number}
                  type="button"
                  role="tab"
                  aria-selected={tab === s.number}
                  title={tr('Дрон {n}', { n: s.number })}
                  onClick={() => {
                    setTab(s.number)
                    onSelect(s.number)
                  }}
                >
                  <span className="sr-num">{s.number}</span>
                  <span className="sr-label">{tr('Дрон {n}', { n: s.number })}</span>
                </button>
              ))}
              {onAddDrone && (
                <button type="button" className="sr-add" title={tr('Добавить дрона: он встанет на свободную клетку')} onClick={onAddDrone}>
                  <span className="sr-num">
                    <Plus size={15} strokeWidth={2} aria-hidden="true" />
                  </span>
                  <span className="sr-label">{tr('Добавить дрона')}</span>
                </button>
              )}
            </div>
          </nav>
        )}
        <div className="codepane-editor">
          <CodeEditor
            key={`${project.key}:${tab}`}
            ref={inner}
            value={value}
            onChange={change}
            marks={tabMarks}
            now={tabNow}
            follow={selected !== null}
          />
        </div>
      </div>
      {run.state === 'error' && (
        <button type="button" className="codepane-error" onClick={() => run.line && onGoto(run.line)}>
          {tr(run.error ?? '')}
        </button>
      )}
    </section>
  )
}
