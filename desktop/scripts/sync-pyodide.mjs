// Copies the Pyodide runtime (Python in WebAssembly) from node_modules into the renderer's public folder, so the app
// loads it from its own files and needs no network. Runs before dev and build.
import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const from = join(root, 'node_modules', 'pyodide')
const to = join(root, 'src', 'renderer', 'public', 'pyodide')
mkdirSync(to, { recursive: true })
for (const name of ['pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json', 'pyodide.mjs']) {
  const src = join(from, name)
  if (!existsSync(src)) throw new Error(`pyodide: missing ${name}, run npm install`)
  copyFileSync(src, join(to, name))
}
console.log('pyodide copied to', to)
