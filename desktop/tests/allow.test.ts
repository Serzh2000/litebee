import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, describe, expect, it } from 'vitest'
import { loadAllowed, saveAllowed } from '../src/main/allow'

const dir = mkdtempSync(join(tmpdir(), 'litebee-allow-'))
afterAll(() => rmSync(dir, { recursive: true, force: true }))

describe('the permission to poll the drones', () => {
  it('is off when nothing was ever chosen', () => {
    expect(loadAllowed(join(dir, 'missing.json'))).toBe(false)
  })

  it('is off for a file that cannot be read', () => {
    const file = join(dir, 'broken.json')
    writeFileSync(file, '{not json')
    expect(loadAllowed(file)).toBe(false)
    writeFileSync(file, JSON.stringify({ pollDrones: 'yes' }))
    expect(loadAllowed(file)).toBe(false)
  })

  it('keeps what the person chose', () => {
    const file = join(dir, 'link-settings.json')
    saveAllowed(file, true)
    expect(loadAllowed(file)).toBe(true)
    saveAllowed(file, false)
    expect(loadAllowed(file)).toBe(false)
  })
})
