/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-18
// The busy counter is module state shared by every test in this file, so each
// test lets all of its requests settle before it ends.
import {describe, expect, it} from 'vitest';
import {act, renderHook} from '@testing-library/react';
import {isCaptureBusyError, useCaptureBusy} from './useCaptureBusy';
import {api} from '../api/client';
import {deferred, fakeApi} from '../test/fakeApi';

/**
 * Start a request whose reply waits for the returned release(reply).
 *
 * Async act: axios runs request interceptors (where the counter goes up) a
 * microtask after the call, so a synchronous act would check too early.
 */
const holdRequest = async (send) => {
    const reply = deferred();
    fakeApi(() => reply.promise);
    let settled;
    await act(async () => {
        settled = send().catch(() => {});
    });
    const release = async (response) => {
        await act(async () => {
            reply.resolve(response);
            await settled;
        });
    };
    return release;
};

describe('useCaptureBusy', () => {
    it('is true only while a capture request is in flight', async () => {
        const {result} = renderHook(() => useCaptureBusy());
        expect(result.current).toBe(false);

        const release = await holdRequest(() => api.post('/api/capture-screen/gifts'));
        expect(result.current).toBe(true);

        await release({status: 200, data: {success: true}});
        expect(result.current).toBe(false);
    });

    it('clears after a failed capture too', async () => {
        const {result} = renderHook(() => useCaptureBusy());
        const release = await holdRequest(() => api.post('/api/capture-screen/gifts'));
        expect(result.current).toBe(true);

        await release({status: 500, data: {error: 'Capture failed.'}});
        expect(result.current).toBe(false);
    });

    it("doesn't count background captures or non-capture requests", async () => {
        const {result} = renderHook(() => useCaptureBusy());

        const releaseBackground = await holdRequest(
            () => api.post('/api/capture-screen/combat-refresh', null, {background: true}),
        );
        expect(result.current).toBe(false);
        await releaseBackground({status: 200, data: {}});

        const releaseOrdinary = await holdRequest(() => api.get('/api/factions/summary'));
        expect(result.current).toBe(false);
        await releaseOrdinary({status: 200, data: []});
    });
});

describe('isCaptureBusyError', () => {
    it("recognises only the backend's busy 409", () => {
        const busy = {response: {status: 409, data: {busy: true, error: 'Another capture is running.'}}};
        const conflict = {response: {status: 409, data: {error: 'Name already exists.'}}};
        expect(isCaptureBusyError(busy)).toBe(true);
        expect(isCaptureBusyError(conflict)).toBe(false);
        expect(isCaptureBusyError({})).toBe(false);
    });
});
