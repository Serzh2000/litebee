import type { ShowData } from '@core/show'

export const SHOW_TIMEOUT_MS = 5000

export type RunResult = { ok: ShowData } | { error: string; line: number | null }

/**
 * Runs Python show source and returns the show as data. The Python lives in a worker that is killed when the code runs
 * longer than the time limit (a loop that never ends) and started again for the next run. The first start of the
 * worker loads the interpreter; the limit counts only the user's code.
 */
class Runner {
  private worker: Worker | null = null
  private ready: Promise<void> | null = null
  private nextId = 1

  private start(): Worker {
    const worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' })
    this.worker = worker
    this.ready = new Promise<void>((resolve) => {
      const on = (e: MessageEvent) => {
        if (e.data?.ready) {
          worker.removeEventListener('message', on)
          resolve()
        }
      }
      worker.addEventListener('message', on)
    })
    return worker
  }

  /** Starts loading the interpreter before the first run needs it. */
  warm(): void {
    if (!this.worker) this.start()
  }

  async run(source: string, filename: string): Promise<RunResult> {
    const worker = this.worker ?? this.start()
    await this.ready
    const id = this.nextId++
    const indexURL = new URL('./pyodide/', document.baseURI).href
    return new Promise<RunResult>((resolve) => {
      const timer = setTimeout(() => {
        worker.terminate()
        this.worker = null
        this.ready = null
        resolve({ error: `Шоу выполняется дольше ${SHOW_TIMEOUT_MS / 1000} с. Проверьте циклы в коде`, line: null })
      }, SHOW_TIMEOUT_MS)
      const on = (e: MessageEvent) => {
        if (e.data?.id !== id) return
        clearTimeout(timer)
        worker.removeEventListener('message', on)
        resolve(e.data.result as RunResult)
      }
      worker.addEventListener('message', on)
      worker.postMessage({ id, indexURL, source, filename })
    })
  }
}

export const runner = new Runner()
