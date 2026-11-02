import { projectFileName } from '@core/project'

export interface Opened {
  /** full path in the app; just the file name in a plain browser */
  path: string
  text: string
}

/** The file name from a path of either kind of slash. */
export const baseName = (path: string): string => path.split(/[\\/]/).pop() ?? path

/** Opens a show file (.py): the system dialog in the app, a file picker in a plain browser. Null when cancelled. */
export async function openProjectFile(): Promise<Opened | null> {
  if (window.litebee) return window.litebee.openProject()
  return new Promise((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.py,text/x-python,text/plain'
    input.onchange = async () => {
      const file = input.files?.[0]
      resolve(file ? { path: file.name, text: await file.text() } : null)
    }
    input.oncancel = () => resolve(null)
    input.click()
  })
}

/**
 * Saves the source. In the app: to `path`, or after asking where when it is null. In a plain browser the file goes to
 * downloads under the suggested name. Returns where it went, or null when the person cancelled.
 */
export async function saveProjectFile(text: string, path: string | null, name: string): Promise<{ path: string } | null> {
  const suggested = projectFileName(name, 'py')
  if (window.litebee) return window.litebee.saveProject({ text, path, suggested })
  const url = URL.createObjectURL(new Blob([text], { type: 'text/x-python' }))
  const a = document.createElement('a')
  a.href = url
  a.download = suggested
  a.click()
  URL.revokeObjectURL(url)
  return { path: suggested }
}
