/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// One shared "a capture is running" flag for every page (N-S1).
//
// The backend runs one automation at a time and answers an overlapping request
// with 409. This module counts in-flight /api/capture-screen/ requests made
// through axios, so any page can disable its capture buttons while another
// capture is driving the game. Requests sent with `{ background: true }` in
// the axios config (Combat's periodic refresh) are not counted, so the buttons
// don't flicker every few seconds.
import axios from 'axios';
import { useSyncExternalStore } from 'react';

const CAPTURE_PREFIX = '/api/capture-screen/';
const TRACKED = Symbol('captureTracked');

let inFlight = 0;
const listeners = new Set();

const notify = () => listeners.forEach((listener) => listener());

const finish = (config) => {
  if (config?.[TRACKED]) {
    config[TRACKED] = false;
    inFlight -= 1;
    notify();
  }
};

axios.interceptors.request.use((config) => {
  if (config.url?.startsWith(CAPTURE_PREFIX) && !config.background) {
    config[TRACKED] = true;
    inFlight += 1;
    notify();
  }
  return config;
});

axios.interceptors.response.use(
  (response) => {
    finish(response.config);
    return response;
  },
  (error) => {
    finish(error.config);
    return Promise.reject(error);
  },
);

const subscribe = (listener) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

const getSnapshot = () => inFlight > 0;

/** True while any foreground capture request is in flight, from any page. */
export function useCaptureBusy() {
  return useSyncExternalStore(subscribe, getSnapshot);
}

/** True for the backend's "another capture is in progress" 409. */
export function isCaptureBusyError(error) {
  return error?.response?.status === 409 && error.response.data?.busy === true;
}
