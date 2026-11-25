import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { HighlightStyle, bracketMatching, indentOnInput, syntaxHighlighting } from '@codemirror/language'
import { autocompletion, completionKeymap, snippetCompletion, type CompletionContext, type CompletionResult } from '@codemirror/autocomplete'
import { python } from '@codemirror/lang-python'
import { setDiagnostics, type Diagnostic } from '@codemirror/lint'
import { EditorState, StateEffect, StateField, type Range } from '@codemirror/state'
import reference from '../data/reference.json'
import { Decoration, type DecorationSet, EditorView, type Tooltip, drawSelection, hoverTooltip, highlightActiveLine, highlightActiveLineGutter, keymap, lineNumbers, showTooltip } from '@codemirror/view'
import { tags } from '@lezer/highlight'
import './CodeEditor.css'
import { tr } from '@core/i18n'
import { LED_COLORS, NOTE_SECONDS, PIANO, buzzArgsAt, colorText, hexToRgb, parseColorArg, rgbArgAt, rgbToHex, snippetFor } from '@core/hints'

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
  owner: string
  kind: string
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


const translated = (text: string): string => tr(text)

/**
 * Suggestions while typing: after `d.` the commands of a drone (after `show.` those of the show) with their signature and
 * the same explanation as the hover help; inside `d.rgb(` the names of the colours. A command is inserted with a place for
 * every argument (Tab goes to the next).
 */
function suggest(context: CompletionContext): CompletionResult | null {
  const line = context.state.doc.lineAt(context.pos)
  const col = context.pos - line.from
  if (rgbArgAt(line.text, col)) {
    const word = context.matchBefore(/['"]?\w*/)
    if (!word || (word.from === word.to && !context.explicit)) return null
    const quote = /^['"]/.exec(word.text)?.[0] ?? "'"
    return {
      from: word.from,
      options: LED_COLORS.map((c, i) => ({ label: `${quote}${c.name}${quote}`, type: 'constant', detail: String(i), boost: -i })),
      validFor: /^['"]?\w*$/,
    }
  }
  const buzz = buzzArgsAt(line.text, col)
  if (buzz && buzz.args.length <= 1) {
    const word = context.matchBefore(/['"]?[A-Za-z]*\d?/)
    if (!word || (word.from === word.to && !context.explicit)) return null
    const quote = /^['"]/.exec(word.text)?.[0] ?? "'"
    return {
      from: word.from,
      options: PIANO.map((k, i) => ({ label: `${quote}${k.name}${quote}`, type: 'constant', detail: String(k.index), boost: -i })),
      validFor: /^['"]?[A-Za-z]*\d?$/,
    }
  }
  const dot = context.matchBefore(/[A-Za-z_]\w*\.\w*/)
  if (!dot) return null
  const receiver = dot.text.slice(0, dot.text.indexOf('.'))
  const owner = receiver === 'show' ? 'Show' : 'Drone'
  const from = dot.from + dot.text.indexOf('.') + 1
  const options = (reference.entries as RefEntry[])
    .filter((e) => e.owner === owner && e.kind === 'method')
    .map((e) => ({
      ...snippetCompletion(snippetFor(e.signature), { label: e.name, type: 'method', detail: e.signature.slice(e.name.length), info: () => helpNode(e) }),
    }))
  return { from, options, validFor: /^\w*$/ }
}

function helpNode(entry: RefEntry): HTMLElement {
  const dom = el('div', 'cm-ref')
  dom.append(el('p', 'cm-ref-sum', translated(entry.summary)), el('p', 'cm-ref-status', `${entry.icon} ${translated(entry.status)}`))
  return dom
}

/**
 * The colour panel: while the cursor stands inside the colour of `d.rgb(...)`, the eight colours of the LEDs and a free
 * choice sit under it. A click writes the colour into the code, so the code stays the one truth and Ctrl+Z takes it back.
 */
const colorPanel = StateField.define<Tooltip | null>({
  create: () => null,
  update(prev, tr) {
    if (!tr.docChanged && !tr.selection && prev !== null) return prev
    const head = tr.state.selection.main.head
    const line = tr.state.doc.lineAt(head)
    const arg = rgbArgAt(line.text, head - line.from)
    if (!arg) return null
    const pos = line.from + arg.from
    // the same panel while the colour is being changed: rebuilding it would close the open colour chooser
    if (prev && prev.pos === pos) return prev
    return { pos, above: false, strictSide: true, arrow: false, create: createColorPanel }
  },
  provide: (f) => showTooltip.from(f),
})

function createColorPanel(view: EditorView) {
  const dom = el('div', 'cm-colors')
  // the editor keeps the cursor while a swatch is pressed
  dom.addEventListener('mousedown', (e) => {
    if ((e.target as HTMLElement).tagName !== 'INPUT') e.preventDefault()
  })
  const put = (text: string) => {
    const head = view.state.selection.main.head
    const line = view.state.doc.lineAt(head)
    const arg = rgbArgAt(line.text, head - line.from)
    if (!arg) return
    view.dispatch({ changes: { from: line.from + arg.from, to: line.from + arg.to, insert: text }, selection: { anchor: line.from + arg.from + text.length } })
  }
  for (const c of LED_COLORS) {
    const b = el('button', 'cm-color') as HTMLButtonElement
    b.type = 'button'
    b.title = c.name
    b.setAttribute('aria-label', c.name)
    b.style.background = `rgb(${c.rgb.join(' ')})`
    b.addEventListener('click', () => put(colorText(c.rgb)))
    dom.append(b)
  }
  const free = el('input', 'cm-color-free') as HTMLInputElement
  free.type = 'color'
  free.title = tr('Свой цвет')
  free.setAttribute('aria-label', tr('Свой цвет'))
  const head = view.state.selection.main.head
  const line = view.state.doc.lineAt(head)
  const arg = rgbArgAt(line.text, head - line.from)
  free.value = rgbToHex(parseColorArg(arg ? line.text.slice(arg.from, arg.to) : '') ?? [255, 128, 0])
  free.addEventListener('input', () => put(colorText(hexToRgb(free.value))))
  free.addEventListener('change', () => view.focus())
  dom.append(free)
  return { dom }
}

/**
 * The note panel: while the cursor stands inside `d.buzz(...)`, a small piano (C3 to G4, the notes that were checked by
 * ear) and the usual lengths sit under it. A key writes the note into the code, a length writes the seconds; the code
 * stays the one truth and Ctrl+Z takes the change back.
 */
const notePanel = StateField.define<Tooltip | null>({
  create: () => null,
  update(prev, tr) {
    if (!tr.docChanged && !tr.selection && prev !== null) return prev
    const head = tr.state.selection.main.head
    const line = tr.state.doc.lineAt(head)
    const call = buzzArgsAt(line.text, head - line.from)
    if (!call) return null
    const pos = line.from + call.from
    if (prev && prev.pos === pos) return prev
    return { pos, above: false, strictSide: true, arrow: false, create: createNotePanel }
  },
  provide: (f) => showTooltip.from(f),
})

const KEY_W = 22

function createNotePanel(view: EditorView) {
  const dom = el('div', 'cm-notes')
  dom.addEventListener('mousedown', (e) => e.preventDefault())
  /** Writes `text` over argument `n` of the call under the cursor (or adds it after the previous one). */
  const put = (n: 0 | 1, text: string) => {
    const head = view.state.selection.main.head
    const line = view.state.doc.lineAt(head)
    const call = buzzArgsAt(line.text, head - line.from)
    if (!call) return
    const base = line.from
    const arg = call.args[n]
    if (arg) {
      view.dispatch({ changes: { from: base + arg.from, to: base + arg.to, insert: text }, selection: { anchor: base + arg.from + text.length } })
    } else if (n === 1 && call.args[0]) {
      const at = base + call.args[0].to
      view.dispatch({ changes: { from: at, insert: `, ${text}` }, selection: { anchor: at + 2 + text.length } })
    } else {
      view.dispatch({ changes: { from: base + call.from, to: base + call.to, insert: text }, selection: { anchor: base + call.from + text.length } })
    }
  }
  const keys = el('div', 'cm-piano')
  let whites = 0
  keys.style.width = `${PIANO.filter((k) => !k.black).length * KEY_W}px`
  for (const k of PIANO) {
    const b = el('button', k.black ? 'cm-key cm-key-black' : 'cm-key') as HTMLButtonElement
    b.type = 'button'
    b.title = k.name
    b.setAttribute('aria-label', tr('Нота {n}', { n: k.name }))
    if (k.black) b.style.left = `${whites * KEY_W - 7}px`
    else {
      b.style.left = `${whites * KEY_W}px`
      if (k.name.startsWith('C')) b.textContent = k.name
      whites++
    }
    b.addEventListener('click', () => {
      const head = view.state.selection.main.head
      const line = view.state.doc.lineAt(head)
      const call = buzzArgsAt(line.text, head - line.from)
      put(0, `'${k.name}'`)
      // a new call gets a length too, so it is complete at once
      if (call && call.args.length < 2) put(1, '0.5')
    })
    keys.append(b)
  }
  const lengths = el('div', 'cm-lengths')
  for (const s of NOTE_SECONDS) {
    const b = el('button', 'cm-length', `${s}`) as HTMLButtonElement
    b.type = 'button'
    b.title = tr('Длительность {s} с', { s })
    b.setAttribute('aria-label', tr('Длительность {s} с', { s }))
    b.addEventListener('click', () => put(1, `${s}`))
    lengths.append(b)
  }
  dom.append(keys, lengths)
  return { dom }
}

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
  '.cm-scroller': { fontFamily: 'var(--font-num)', fontSize: '13px', lineHeight: '1.6' },
  '.cm-gutters': { backgroundColor: 'var(--desk)', color: 'var(--ink-3)', border: 'none', borderRight: '1px solid var(--border)' },
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
          autocompletion({ override: [suggest], icons: false }),
          colorPanel,
          notePanel,
          keymap.of([...completionKeymap, indentWithTab, ...defaultKeymap, ...historyKeymap]),
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
