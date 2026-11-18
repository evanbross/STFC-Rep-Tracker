/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-18
// Runs before every test file (vite.config.js test.setupFiles).
import {afterEach, vi} from 'vitest';
import {cleanup} from '@testing-library/react';
import {restoreApiAdapter} from './fakeApi';

afterEach(() => {
    // Testing Library only auto-cleans when Vitest globals are on; they're off.
    cleanup();
    restoreApiAdapter();
    vi.restoreAllMocks();
});
