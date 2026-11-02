import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'electron-vite'

const alias = { '@core': resolve('src/core'), '@renderer': resolve('src/renderer/src') }

export default defineConfig({
  main: { resolve: { alias } },
  preload: { resolve: { alias } },
  renderer: {
    resolve: { alias },
    plugins: [react()],
    // The show editor runs the DSL files of the Python app (../litebee/*.py) as they are.
    server: { fs: { allow: [resolve('..')] } },
    worker: { format: 'es' },
  },
})
