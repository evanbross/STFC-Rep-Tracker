/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-19
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {act, renderHook, waitFor} from '@testing-library/react';
import useCommunityModStatus, {EVENTS_URL, STATUS_URL} from './useCommunityModStatus';
import {formatSyncTime} from './CommunityModStatus';
import {fakeApi, NETWORK_ERROR} from '../../test/fakeApi';

const FIRST = '2026-11-19T04:09:06+00:00';
const LATER = '2026-11-19T04:09:43+00:00';

/** jsdom has no EventSource; this one lets a test fire the browser's events by hand. */
class FakeEventSource {
    static instances = [];

    constructor(url) {
        this.url = url;
        this.listeners = {};
        this.closed = false;
        FakeEventSource.instances.push(this);
    }

    addEventListener(type, listener) {
        (this.listeners[type] ??= []).push(listener);
    }

    close() {
        this.closed = true;
    }

    emit(type, data) {
        for (const listener of this.listeners[type] ?? []) listener({data});
    }
}

const source = () => FakeEventSource.instances.at(-1);

beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal('EventSource', FakeEventSource);
});

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('useCommunityModStatus', () => {
    it('loads the last sync time and subscribes to capture events', async () => {
        const requests = fakeApi(() => ({status: 200, data: {last_received_at: FIRST}}));

        const {result} = renderHook(() => useCommunityModStatus());

        await waitFor(() => expect(result.current.lastReceivedAt).toBe(FIRST));
        expect(requests.map((r) => r.url)).toEqual([STATUS_URL]);
        expect(source().url).toBe(EVENTS_URL);
    });

    it('takes the time from a capture event without another request', async () => {
        const requests = fakeApi(() => ({status: 200, data: {last_received_at: FIRST}}));
        const {result} = renderHook(() => useCommunityModStatus());
        await waitFor(() => expect(result.current.lastReceivedAt).toBe(FIRST));

        act(() => source().emit('capture', JSON.stringify({last_received_at: LATER})));

        expect(result.current.lastReceivedAt).toBe(LATER);
        expect(requests).toHaveLength(1);
    });

    it('re-reads the status after the stream reconnects, but not on the first open', async () => {
        let current = FIRST;
        const requests = fakeApi(() => ({status: 200, data: {last_received_at: current}}));
        const {result} = renderHook(() => useCommunityModStatus());
        await waitFor(() => expect(result.current.lastReceivedAt).toBe(FIRST));

        act(() => source().emit('open'));
        expect(requests).toHaveLength(1);

        current = LATER;   // a sync landed while the stream was down
        act(() => {
            source().emit('error');
            source().emit('open');
        });

        await waitFor(() => expect(result.current.lastReceivedAt).toBe(LATER));
        expect(requests).toHaveLength(2);
    });

    // ai: claude-opus-5-5 | 2026-11-19
    it('calls onReadingsSaved for a readings event and after a reconnect', async () => {
        fakeApi(() => ({status: 200, data: {last_received_at: FIRST}}));
        const onReadingsSaved = vi.fn();
        const {result} = renderHook(() => useCommunityModStatus({onReadingsSaved}));
        await waitFor(() => expect(result.current.lastReceivedAt).toBe(FIRST));

        act(() => source().emit('open'));
        expect(onReadingsSaved).not.toHaveBeenCalled();

        act(() => source().emit('readings', '{}'));
        expect(onReadingsSaved).toHaveBeenCalledTimes(1);

        act(() => {
            source().emit('error');
            source().emit('open');
        });
        expect(onReadingsSaved).toHaveBeenCalledTimes(2);
    });

    it('works without an onReadingsSaved callback', async () => {
        fakeApi(() => ({status: 200, data: {last_received_at: FIRST}}));
        const {result} = renderHook(() => useCommunityModStatus());
        await waitFor(() => expect(result.current.lastReceivedAt).toBe(FIRST));

        act(() => source().emit('readings', '{}'));

        expect(result.current.error).toBeNull();
    });

    it('reports an error when the status cannot be loaded', async () => {
        fakeApi(() => NETWORK_ERROR);

        const {result} = renderHook(() => useCommunityModStatus());

        await waitFor(() => expect(result.current.error).toMatch(/Cannot reach the server/));
        expect(result.current.lastReceivedAt).toBeNull();
    });

    it('closes the stream on unmount', async () => {
        fakeApi(() => ({status: 200, data: {last_received_at: null}}));
        const {unmount} = renderHook(() => useCommunityModStatus());

        unmount();

        expect(source().closed).toBe(true);
    });
});

describe('formatSyncTime', () => {
    it('says never when nothing has been received', () => {
        expect(formatSyncTime(null)).toBe('never');
    });

    it('shows a received time as a local date and time', () => {
        expect(formatSyncTime(FIRST)).toBe(
            new Date(FIRST).toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'medium'}),
        );
    });
});
