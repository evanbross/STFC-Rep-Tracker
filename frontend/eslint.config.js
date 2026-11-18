/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-18
// Lint for what `vite build` can't see: names undefined only on a runtime
// branch (no-undef), and hooks called conditionally or with stale deps.
import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'

export default [
  { ignores: ['dist/'] },
  js.configs.recommended,
  reactHooks.configs.flat.recommended,
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    // ai: claude-opus-5-5 | 2026-11-18
    // Dialog globals must be called as window.alert / window.confirm /
    // window.prompt (JAVASCRIPT_TYPESCRIPT_STANDARDS.md). Member access isn't a
    // global reference, so only the bare forms are flagged.
    rules: {
      'no-restricted-globals': ['error',
        { name: 'alert', message: 'Use window.alert().' },
        { name: 'confirm', message: 'Use window.confirm().' },
        { name: 'prompt', message: 'Use window.prompt().' },
      ],
    },
  },
  {
    files: ['*.config.js'],
    languageOptions: { globals: globals.node },
  },
]
