import { useEffect, useImperativeHandle, useMemo, useRef, type Ref } from 'react'
import { joinDrones, splitDrones } from '@core/sections'
import type { Project } from '../App'
import { CodeEditor, type CodeEditorHandle } from './CodeEditor'
import './DroneEditor.css'
import { tr } from '@core/i18n'

interface Props {
  project: Project
  drone: number
  marks: { line: number; level: 'error' | 'warning' | 'info'; message: string }[]
  /** the handle the rest of the app uses; its lines are lines of the whole text, this maps them onto the drone */
  editor: Ref<CodeEditorHandle>
  onSource: (text: string) => void
  now: { run: number[]; light: number[] }
  /** a line of the whole text to put the cursor on once this drone's code is on the screen */
  goto: number | null
  onGotoDone: () => void
}

/**
 * The program of ONE drone. The project is still one text under the hood, but it is never shown whole: the editor holds
 * the block of the drone that was picked on the scene and writes its changes back into the right place. A text that
 * cannot be cut by drone (a loop makes the drones) is shown whole, with a note, because there is nothing to cut.
 */
export function DroneEditor({ project, drone, marks, editor, onSource, now, goto, onGotoDone }: Props) {
  const split = useMemo(() => splitDrones(project.source), [project.source])
  const section = split?.sections.find((s) => s.number === drone) ?? null
  const inner = useRef<CodeEditorHandle | null>(null)

  const shift = section ? section.line - 1 : 0
  const inView = (line: number) => !section || (line >= section.line && line < section.line + section.lines)

  const tabMarks = useMemo(
    () => marks.filter((m) => inView(m.line)).map((m) => ({ ...m, line: m.line - shift })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [marks, section],
  )
  const tabNow = useMemo(
    () => ({ run: now.run.filter(inView).map((l) => l - shift), light: now.light.filter(inView).map((l) => l - shift) }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [now, section],
  )

  useImperativeHandle(editor, () => ({
    reveal: (line) => {
      if (inView(line)) inner.current?.reveal(line - shift)
    },
    insert: (text) => inner.current?.insert(text),
    replace: (text) => onSource(text),
  }))

  useEffect(() => {
    if (goto === null || !inView(goto)) return
    inner.current?.reveal(goto - shift)
    onGotoDone()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [goto, section?.number])

  const value = section ? section.text : project.source
  const change = (text: string) => onSource(section && split ? joinDrones(split, section.number, text) : text)

  return (
    <div className="deditor" aria-label={tr('Программа дрона {n}', { n: drone })}>
      {!section && <p className="deditor-note">{tr('Дроны этого шоу создаёт общий цикл, поэтому код показан целиком.')}</p>}
      <div className="deditor-box">
        <CodeEditor key={`${project.key}:${drone}`} ref={inner} value={value} onChange={change} marks={tabMarks} now={tabNow} follow />
      </div>
    </div>
  )
}
