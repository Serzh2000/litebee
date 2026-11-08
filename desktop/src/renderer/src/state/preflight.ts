export type StepState = 'done' | 'current' | 'next' | 'blocked'

export interface PreflightStep {
  label: string
  state: StepState
  word: string
  error?: boolean
  why?: string
}

export interface PreflightInput {
  /** null: never checked; 'stale': the show or the limit changed since the check */
  check: null | 'stale' | 'ok' | 'errors'
  errors: number
  connected: boolean
  /** why the show cannot be put on board now (null: it can) */
  loadBlock: string | null
  /** the upload is under way */
  loading: boolean
  /** every drone that got a role holds the current show */
  loaded: boolean
  /** the drones are armed */
  armed: boolean
  /** a mission is running */
  flying: boolean
}

/**
 * The four steps before a flight. A step is done, current (the next thing to do and possible now: filled), next (the
 * next thing to do but blocked: outlined in the accent) or blocked (later: dim). The words say what the icons say.
 * Loading needs a drone on the link that has been given a role; arming and starting are not ported yet and stay blocked.
 */
export function preflight({ check, errors, connected, loadBlock, loading, loaded, armed, flying }: PreflightInput): { steps: PreflightStep[]; reason: string; cta: boolean } {
  const labels = ['Проверить', 'Загрузить', 'Взвести', 'Старт']
  const blocked = (label: string): PreflightStep => ({ label, state: 'blocked', word: 'позже' })

  if (check === null || check === 'stale') {
    return {
      steps: [
        { label: labels[0], state: 'current', word: check === null ? 'нужна' : 'устарела' },
        ...labels.slice(1).map(blocked),
      ],
      reason: check === null ? 'Нажмите «Проверить»' : 'Шоу или лимит изменились: нажмите «Проверить» ещё раз',
      cta: true,
    }
  }
  if (check === 'errors') {
    return {
      steps: [
        { label: labels[0], state: 'current', word: 'есть ошибки', error: true },
        ...labels.slice(1).map(blocked),
      ],
      reason: `В проверках ${errors} ${errors === 1 ? 'ошибка' : 'ошибок'}: исправьте шоу или поднимите лимит высоты`,
      cta: false,
    }
  }
  if (flying) {
    return {
      steps: [
        { label: labels[0], state: 'done', word: 'пройдена' },
        { label: labels[1], state: 'done', word: 'загружено' },
        { label: labels[2], state: 'done', word: 'взведён' },
        { label: labels[3], state: 'next', word: 'летит' },
      ],
      reason: 'Идёт полёт. Esc или красная кнопка: аварийная посадка',
      cta: false,
    }
  }
  const load: PreflightStep = loaded
    ? { label: labels[1], state: 'done', word: 'загружено' }
    : loading
      ? { label: labels[1], state: 'current', word: 'идёт…' }
      : loadBlock
        ? { label: labels[1], state: 'next', word: 'недоступно', why: loadBlock }
        : { label: labels[1], state: 'current', word: 'можно' }
  const arm: PreflightStep = !loaded
    ? blocked(labels[2])
    : armed
      ? { label: labels[2], state: 'done', word: 'взведён', why: 'Нажмите, чтобы снять' }
      : { label: labels[2], state: 'current', word: 'можно' }
  const start: PreflightStep = !loaded || !armed ? blocked(labels[3]) : { label: labels[3], state: 'current', word: 'можно' }
  return {
    steps: [{ label: labels[0], state: 'done', word: 'пройдена' }, load, arm, start],
    reason: loading
      ? 'Загружаю миссию в дроны…'
      : !loaded
        ? loadBlock ??
          (connected ? 'Нажмите «Загрузить»: миссия уйдёт в выбранные дроны' : 'Дронов на связи нет: шоу можно писать, смотреть и проверять, но не летать')
        : !armed
          ? 'Миссия на борту. Нажмите «Взвести»: это разрешает старт'
          : 'Взведено. Нажмите «Старт»: дроны полетят после вашего подтверждения. Снять взвод: ещё раз «Взвести»',
    cta: !loading && (loaded || (!loadBlock && connected)),
  }
}

/** Whether the step `i` can be pressed now: checking always; loading when it is possible; arming (and disarming); the start. */
export function canPress(steps: PreflightStep[], i: number): boolean {
  const s = steps[i]
  if (!s) return false
  return i === 0 || (i === 1 && s.state === 'current' && s.word === 'можно') || (i === 2 && (s.state === 'current' || s.word === 'взведён')) || (i === 3 && s.state === 'current')
}

/** The step that the primary button of the screen does: the first one that is not done, or null while the drones fly. */
export function nextStep(steps: PreflightStep[], flying: boolean): number | null {
  if (flying) return null
  const i = steps.findIndex((s) => s.state !== 'done')
  return i < 0 ? null : i
}

/**
 * Quiet notes about what nobody has flown yet, shown under the chain. `drones` is the number of drones of the show,
 * `unproven` the number of drones holding a step that is not proven on a real drone (see core/mission.ts unprovenSteps).
 */
export function honestyNotes(drones: number, unproven: number): string[] {
  const out: string[] = []
  if (drones > 1) out.push('Несколько дронов вместе пока не проверены в полёте')
  if (unproven > 0) out.push('В шоу есть шаги, не проверенные на дроне')
  return out
}
