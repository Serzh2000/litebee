import { ArrowRight, Code, Play } from 'lucide-react'
import type { Mode, Project, ProjectActions } from '../App'
import { Preflight } from './Preflight'
import { Emergency } from './Emergency'
import { Mark } from './Mark'
import { LinkChip } from './LinkChip'
import { ProjectMenu } from './ProjectMenu'
import type { PreflightStep } from '../state/preflight'
import type { Link } from '../state/useLink'
import './TopBar.css'
import { tr } from '@core/i18n'

interface Props {
  project: Project
  actions: ProjectActions
  steps: PreflightStep[]
  reason: string
  /** the reason says what to press next */
  cta: boolean
  onCheck: () => void
  mode: Mode
  onMode: (m: Mode) => void
  link: Link
  onStep: (i: number) => void
  onEmergency: () => void
}

export function TopBar({ project, actions, steps, reason, cta, onCheck, mode, onMode, link, onStep, onEmergency }: Props) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <Mark />
        <ProjectMenu project={project} actions={actions} />
      </div>

      <div className="mode" role="group" aria-label={tr('Вид')}>
        <button type="button" aria-pressed={mode === 'code'} onClick={() => onMode('code')}>
          <Code size={15} strokeWidth={1.9} aria-hidden="true" />
          {tr('Код')}
        </button>
        <button type="button" aria-pressed={mode === 'map'} onClick={() => onMode('map')}>
          <Play size={15} strokeWidth={1.9} aria-hidden="true" />
          {tr('Симуляция')}
        </button>
      </div>

      <div className="topbar-right">
        <LinkChip link={link} />
        <div className="topbar-chain">
          <Preflight steps={steps} onStep={(i) => (i === 0 ? onCheck() : onStep(i))} />
          <p className="reason" role="status" data-cta={cta}>
            {cta && <ArrowRight size={13} strokeWidth={2.4} aria-hidden="true" />}
            {tr(reason)}
          </p>
        </div>
        <Emergency onPress={onEmergency} compact />
      </div>
    </header>
  )
}
