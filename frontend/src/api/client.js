/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// The one axios instance every page uses (N-O6), plus the shared error text.
//
// Paths stay absolute ('/api/...'): the Vite dev server proxies /api to Flask,
// and in production Flask serves the UI from the same origin.
import axios from 'axios';

export const CAPTURE_PREFIX = '/api/capture-screen/';

// Ordinary requests answer in well under a second. Captures drive the game UI
// and a full reputation sweep can take minutes, so they get a long ceiling
// instead of none, which means a wedged automation still surfaces as an error.
const DEFAULT_TIMEOUT_MS = 30_000;
const CAPTURE_TIMEOUT_MS = 10 * 60_000;
// ai: claude-opus-5-5 | 2026-11-07
// POST /api/calendar/auth answers only after the user finishes Google's consent
// page, which routinely takes longer than the default ceiling.
export const INTERACTIVE_AUTH_TIMEOUT_MS = 5 * 60_000;

export const SERVER_UNREACHABLE = 'Cannot reach the server. Is the backend running?';
const SERVER_TIMEOUT = 'The server took too long to respond.';

export const api = axios.create({ timeout: DEFAULT_TIMEOUT_MS });

api.interceptors.request.use((config) => {
  if (config.url?.startsWith(CAPTURE_PREFIX)) {
    config.timeout = CAPTURE_TIMEOUT_MS;
  }
  return config;
});

/**
 * Text to show the user for a failed request.
 *
 * The backend's `{"error": ...}` body when there is one (its messages are
 * written for the user), a connection or timeout message when no response
 * arrived, else `fallback`.
 */
export function errorMessage(error, fallback = 'Request failed.') {
  if (!error?.response) {
    return error?.code === 'ECONNABORTED' ? SERVER_TIMEOUT : SERVER_UNREACHABLE;
  }
  // ai: claude-opus-5-5 | 2026-11-17
  // A non-JSON reply (an HTML error page, a proxy's 502) has no message of its
  // own; the status at least says what kind of failure it was.
  return error.response.data?.error ?? `${fallback} (HTTP ${error.response.status})`;
}
