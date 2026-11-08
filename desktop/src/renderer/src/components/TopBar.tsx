import { ArrowRight, Info, PanelRight, Save, TriangleAlert } from 'lucide-react'
import type { Mode, Project, ProjectActions } from '../App'
import { ProjectMenu } from './ProjectMenu'
import { Preflight } from './Preflight'
import { Emergency } from './Emergency'
import type { PreflightStep } from '../state/preflight'
import './TopBar.css'
import { tr } from '@core/i18n'

interface Props {
  mode: Mode
  project: Project
  actions: ProjectActions
  steps: PreflightStep[]
  onCheck: () => void
  onStep: (i: number) => void
  onEmergency: () => void
  status: 'sim' | 'armed' | 'flying'
  /** the one finding of the screen: what most needs attention before a flight */
  finding: { tone: 'warning' | 'negative' | 'info' | 'next'; text: string }
  onSave: () => void
  inspectorOpen: boolean
  onInspector: () => void
}

const STATUS = {
  sim: { word: 'Симуляция', tone: undefined },
  armed: { word: 'Взведено', tone: 'warning' },
  flying: { word: 'Летит', tone: 'positive' },
} as const

/**
 * The top half of the frame, 48 px on the frame ground with no rule under it: the project and its state, the four
 * steps before a flight as one stepper, the one finding, save and the inspector, and the emergency landing, which is
 * on screen at every width (Esc does the same). The scene below gets the rest of the window.
 */
export function TopBar({ project, actions, steps, onCheck, onStep, onEmergency, status, finding, onSave, inspectorOpen, onInspector }: Props) {
  const Icon = finding.tone === 'info' ? Info : finding.tone === 'next' ? ArrowRight : TriangleAlert
  return (
    <header className="topbar">
      <div className="workspace-project">
        <ProjectMenu project={project} actions={actions} />
        <span className="pill" data-tone={STATUS[status].tone}>
          {tr(STATUS[status].word)}
        </span>
      </div>
      <div className="topbar-chain">
        <Preflight steps={steps} onStep={(i) => (i === 0 ? onCheck() : onStep(i))} />
      </div>
      <div className="topbar-right">
        <p className="finding-chip" data-tone={finding.tone} title={finding.text}>
          <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
          <span>{finding.text}</span>
        </p>
        <button type="button" className="btn btn-icon" onClick={onSave} title={tr('Сохранить') + ' (Ctrl S)'} aria-label={tr('Сохранить')}>
          <Save size={16} aria-hidden="true" />
        </button>
        <button type="button" className="btn btn-icon inspector-toggle" aria-pressed={inspectorOpen} onClick={onInspector} title={tr('Инспектор')} aria-label={tr('Инспектор')}>
          <PanelRight size={16} aria-hidden="true" />
        </button>
        <Emergency onPress={onEmergency} />
      </div>
    </header>
  )
}
