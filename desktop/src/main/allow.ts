/**
 * The permission to poll the drones, kept between runs in a small file of the user's data folder. While it is off the
 * app sends nothing to the network (no announcements, no time sync) and so does not take drones from another computer
 * on the same router. A missing or unreadable file means off: polling is something a person turns on.
 */
import { readFileSync, writeFileSync } from 'node:fs'

export function loadAllowed(file: string): boolean {
  try {
    return (JSON.parse(readFileSync(file, 'utf8')) as { pollDrones?: unknown }).pollDrones === true
  } catch {
    return false
  }
}

export function saveAllowed(file: string, on: boolean): void {
  try {
    writeFileSync(file, JSON.stringify({ pollDrones: on }))
  } catch {
    /* the choice then lasts until the app closes */
  }
}
