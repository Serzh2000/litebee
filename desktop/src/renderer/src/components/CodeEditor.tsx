import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { HighlightStyle, bracketMatching, indentOnInput, syntaxHighlighting } from '@codemirror/language'
import { python } from '@codemirror/lang-python'
import { setDiagnostics, type Diagnostic } from '@codemirror/lint'
import { EditorState, StateEffect, StateField, type Range } from '@codemirror/state'
import reference from '../data/reference.json'
import { Decoration, type DecorationSet, EditorView, drawSelection, hoverTooltip, highlightActiveLine, highlightActiveLineGutter, keymap, lineNumbers } from '@codemirror/view'
import { tags } from '@lezer/highlight'
import './CodeEditor.css'
import { tr } from '@core/i18n'

export interface CodeEditorHandle {
  /** Puts the cursor at the start of a line (1-based), scrolls to it and focuses the editor. */
  reveal: (line: number) => void
  /** Types text at the cursor, on a line of its own. */
  insert: (text: string) => void
  /** Swaps the whole text as one edit, so Ctrl+Z brings the old text back. */
  replace: (text: string) => void
}

interface Props {
  value: string
  onChange: (text: string) => void
  /** Problems to underline: the error of the run, then the findings of the check. */
  marks: { line: number; level: 'error' | 'warning' | 'info'; message: string }[]
  /** Lines in effect at the time on the count sheet: the running step (strong) and the last colour (light). */
  now: { run: number[]; light: number[] }
  /** Scroll the running line into view when it changes. */
  follow: boolean
}

interface RefEntry {
  name: string
  signature: string
  summary: string
  status: string
  icon: string
  params: { name: string; unit: string; text: string }[]
  example: string
}

const BY_NAME = new Map<string, RefEntry>()
for (const e of reference.entries as RefEntry[]) if (!BY_NAME.has(e.name)) BY_NAME.set(e.name, e)

const el = (tag: string, cls: string, text?: string): HTMLElement => {
  const node = document.createElement(tag)
  node.className = cls
  if (text !== undefined) node.textContent = text
  return node
}

/** Hover help: the reference entry of the command under the pointer (the same texts as the «Справочник» tab). */
const referenceTooltip = hoverTooltip((view, pos) => {
  const line = view.state.doc.lineAt(pos)
  for (const m of line.text.matchAll(/[A-Za-z_]\w*/g)) {
    const from = line.from + (m.index ?? 0)
    const to = from + m[0].length
    if (pos < from || pos > to) continue
    // a call looks like `.name(` or `Show(`; a bare variable named like a command is not help-worthy
    const after = line.text[to - line.from]
    const before = line.text[from - line.from - 1]
    if (after !== '(' && before !== '.') return null
    const entry = BY_NAME.get(m[0])
    if (!entry) return null
    return {
      pos: from,
      end: to,
      above: true,
      create() {
        const dom = el('div', 'cm-ref')
        dom.append(el('code', 'cm-ref-sig', entry.signature), el('p', 'cm-ref-sum', entry.summary))
        for (const p of entry.params) {
          const row = el('p', 'cm-ref-param')
          row.append(el('code', '', p.name), document.createTextNode(` ${p.unit}. ${p.text}`))
          dom.append(row)
        }
        dom.append(el('p', 'cm-ref-status', `${entry.icon} ${entry.status}`))
        return { dom }
      },
    }
  }
  return null
})

const setNow = StateEffect.define<{ run: number[]; light: number[] }>()

/** Highlights of the lines that run now. They live in the editor state, so typing moves them with the text. */
const nowField = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(value, tr) {
    value = value.map(tr.changes)
    for (const e of tr.effects) {
      if (!e.is(setNow)) continue
      const doc = tr.state.doc
      const marks: Range<Decoration>[] = []
      const put = (lines: number[], cls: string) =>
        lines.filter((n) => n >= 1 && n <= doc.lines).forEach((n) => marks.push(Decoration.line({ class: cls }).range(doc.line(n).from)))
      put(e.value.light, 'cm-now-light')
      put(e.value.run, 'cm-now-run')
      value = Decoration.set(marks, true)
    }
    return value
  },
  provide: (f) => EditorView.decorations.from(f),
})

// Colours of the code are the app's own: ink for names, the accent for keywords, quiet grey for comments.
const highlight = HighlightStyle.define([
  { tag: [tags.keyword, tags.controlKeyword, tags.operatorKeyword], color: 'var(--accent)', fontWeight: '600' },
  { tag: [tags.string, tags.special(tags.string)], color: 'var(--ok)' },
  { tag: [tags.number, tags.bool, tags.null], color: 'var(--warn)' },
  { tag: tags.comment, color: 'var(--ink-3)', fontStyle: 'italic' },
  { tag: [tags.function(tags.variableName), tags.function(tags.propertyName)], color: 'var(--ink)', fontWeight: '600' },
])

const theme = EditorView.theme({
  '&': { height: '100%', backgroundColor: 'var(--sheet)', color: 'var(--ink)' },
  '.cm-scroller': { fontFamily: "'Cascadia Mono', Consolas, monospace", fontSize: '13px', lineHeight: '1.6' },
  '.cm-gutters': { backgroundColor: 'var(--desk)', color: 'var(--ink-3)', border: 'none', borderRight: '1px solid var(--rule)' },
  '.cm-activeLine': { backgroundColor: 'var(--active-line)' },
  '.cm-activeLineGutter': { backgroundColor: 'var(--accent-tint)', color: 'var(--ink)' },
  '.cm-cursor': { borderLeftColor: 'var(--ink)' },
  '.cm-selectionBackground, &.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground': {
    backgroundColor: 'var(--accent-tint)',
  },
  '.cm-content': { padding: '8px 0' },
})

export const CodeEditor = forwardRef<CodeEditorHandle, Props>(function CodeEditor({ value, onChange, marks, now, follow }, ref) {
  const host = useRef<HTMLDivElement | null>(null)
  const view = useRef<EditorView | null>(null)
  const change = useRef(onChange)
  change.current = onChange

  useEffect(() => {
    const v = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc: value,
        extensions: [
          lineNumbers(),
          highlightActiveLineGutter(),
          highlightActiveLine(),
          history(),
          drawSelection(),
          indentOnInput(),
          bracketMatching(),
          python(),
          syntaxHighlighting(highlight),
          nowField,
          referenceTooltip,
          keymap.of([indentWithTab, ...defaultKeymap, ...historyKeymap]),
          theme,
          EditorView.contentAttributes.of({ 'aria-label': tr('Код шоу на Python'), spellcheck: 'false' }),
          EditorView.updateListener.of((u) => u.docChanged && change.current(u.state.doc.toString())),
        ],
      }),
    })
    view.current = v
    // Tests and the screenshot tool drive the editor through this handle.
    Object.assign(host.current!, { editorView: v })
    return () => v.destroy()
    // The editor is created once per project (the parent remounts it with a key); later text changes come from typing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const v = view.current
    if (!v) return
    const doc = v.state.doc
    const diagnostics: Diagnostic[] = marks
      .filter((m) => m.line >= 1 && m.line <= doc.lines)
      .map((m) => {
        const line = doc.line(m.line)
        return { from: line.from, to: line.to, severity: m.level, message: m.message }
      })
    v.dispatch(setDiagnostics(v.state, diagnostics))
  }, [marks])

  // The lines that run now; the editor follows the first of them when it is out of sight.
  const lastRun = useRef('')
  useEffect(() => {
    const v = view.current
    if (!v) return
    const key = `${now.run.join(',')}|${now.light.join(',')}`
    if (key === lastRun.current) return
    lastRun.current = key
    const effects: StateEffect<unknown>[] = [setNow.of(now)]
    const first = now.run[0]
    if (follow && first && first <= v.state.doc.lines) {
      effects.push(EditorView.scrollIntoView(v.state.doc.line(first).from, { y: 'nearest', yMargin: 80 }))
    }
    v.dispatch({ effects })
  }, [now, follow])

  useImperativeHandle(ref, () => ({
    reveal(line) {
      const v = view.current
      if (!v || line < 1 || line > v.state.doc.lines) return
      const at = v.state.doc.line(line).from
      v.dispatch({ selection: { anchor: at }, effects: EditorView.scrollIntoView(at, { y: 'center' }) })
      v.focus()
    },
    replace(text) {
      const v = view.current
      if (v) v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: text } })
    },
    insert(text) {
      const v = view.current
      if (!v) return
      const head = v.state.selection.main.head
      const line = v.state.doc.lineAt(head)
      const prefix = line.text.trim() === '' ? '' : '\n'
      const at = line.text.trim() === '' ? line.from : line.to
      const body = `${prefix}${text}\n`
      v.dispatch({ changes: { from: at, to: line.text.trim() === '' ? line.to : at, insert: body }, selection: { anchor: at + body.length } })
      v.focus()
    },
  }))

  return <div className="code" ref={host} />
})
