/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// ai: claude-opus-5-5 | 2026-11-18
// The backend writes the port it serves on to ../.backend-port (main.py
// _publish_dev_port), because the launcher moves off 7300 when it's taken.
// Read once at startup: restart `npm run dev` if the backend comes back on a
// different port.
const DEFAULT_BACKEND_PORT = 7300

const backendPort = () => {
  try {
    const port = Number(readFileSync(new URL('../.backend-port', import.meta.url), 'utf8').trim())
    if (Number.isInteger(port) && port > 0 && port < 65536) return port
  } catch {
    // No backend has started from this checkout yet: use the default.
  }
  return DEFAULT_BACKEND_PORT
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort()}`,
        changeOrigin: true,
      }
    }
  }
})
