/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-18
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {act, renderHook} from '@testing-library/react';
import useCaptures from './useCaptures';
import {deferred, fakeApi} from '../../test/fakeApi';

const FED = {id: 3, name: 'Federation'};

let alertSpy;
beforeEach(() => {
    alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
});

const lastAlert = () => alertSpy.mock.calls.at(-1)[0];

describe('captureScreen', () => {
    it('reloads and lists what a reputation sweep saved', async () => {
        const requests = fakeApi(() => ({
            status: 200,
            data: {saved: [{faction: 'Federation', points: 120}, {faction: 'Romulan', points: 80}], results: []},
        }));
        const onSaved = vi.fn();
        const {result} = renderHook(() => useCaptures({onSaved}));

        await act(() => result.current.captureScreen('reputations'));

        expect(requests[0].url).toBe('/api/capture-screen/reputations');
        expect(onSaved).toHaveBeenCalledOnce();
        expect(lastAlert()).toBe('Saved 2 faction(s):\nFederation: 120\nRomulan: 80');
        expect(result.current.isCapturing).toBe(false);
    });

    it("doesn't reload when the sweep read nothing", async () => {
        fakeApi(() => ({status: 200, data: {saved: [], results: []}}));
        const onSaved = vi.fn();
        const {result} = renderHook(() => useCaptures({onSaved}));

        await act(() => result.current.captureScreen('reputations'));

        expect(onSaved).not.toHaveBeenCalled();
        expect(lastAlert()).toBe('Scan complete — no reputation values could be read.');
    });

    it("shows the backend's busy message and clears the running state", async () => {
        fakeApi(() => ({status: 409, data: {error: 'Another capture is running.', busy: true}}));
        const onSaved = vi.fn();
        const {result} = renderHook(() => useCaptures({onSaved}));

        await act(() => result.current.captureScreen('gifts'));

        expect(lastAlert()).toBe('Error: Another capture is running.');
        expect(onSaved).not.toHaveBeenCalled();
        expect(result.current.isCapturing).toBe(false);
        expect(result.current.anyCaptureRunning).toBe(false);
    });

    it('rejects an unknown screen without sending anything', async () => {
        const requests = fakeApi(() => ({status: 200, data: {}}));
        const {result} = renderHook(() => useCaptures({onSaved: vi.fn()}));

        await expect(result.current.captureScreen('nope')).rejects.toThrow('Unknown capture screen: nope');
        expect(requests).toHaveLength(0);
    });
});

describe('captureFaction', () => {
    it('marks the faction as capturing until the reply arrives', async () => {
        const reply = deferred();
        fakeApi(() => reply.promise);
        const onSaved = vi.fn();
        const {result} = renderHook(() => useCaptures({onSaved}));

        let done;
        await act(async () => {
            done = result.current.captureFaction(FED);
        });
        expect(result.current.capturingFactionId).toBe(FED.id);
        expect(result.current.anyCaptureRunning).toBe(true);

        await act(async () => {
            reply.resolve({status: 200, data: {saved: [{faction: 'Federation', points: 5}], results: []}});
            await done;
        });
        expect(result.current.capturingFactionId).toBe(null);
        expect(result.current.anyCaptureRunning).toBe(false);
        expect(onSaved).toHaveBeenCalledOnce();
        expect(alertSpy).not.toHaveBeenCalled();
    });

    it('says so when the faction could not be read', async () => {
        fakeApi(() => ({status: 200, data: {saved: [], results: []}}));
        const {result} = renderHook(() => useCaptures({onSaved: vi.fn()}));

        await act(() => result.current.captureFaction(FED));

        expect(lastAlert()).toBe('Federation: no reputation value could be read.');
    });
});
