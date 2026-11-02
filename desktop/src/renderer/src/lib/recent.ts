/** The projects opened or saved last, kept in the browser storage of the app: a path and the name to show. */
export interface Recent {
  path: string
  name: string
  at: number
}

const KEY = 'litebee.recent'
const MAX = 6

export function recents(): Recent[] {
  try {
    const list = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(list) ? list.filter((r) => r && typeof r.path === 'string').slice(0, MAX) : []
  } catch {
    return []
  }
}

export function remember(path: string, name: string): void {
  try {
    const next = [{ path, name, at: Date.now() }, ...recents().filter((r) => r.path !== path)].slice(0, MAX)
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    /* no storage: the list stays empty */
  }
}

export function forget(path: string): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(recents().filter((r) => r.path !== path)))
  } catch {
    /* nothing to forget */
  }
}
