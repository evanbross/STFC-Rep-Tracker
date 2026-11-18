/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-18
import {describe, expect, it, vi} from 'vitest';
import {act, renderHook} from '@testing-library/react';
import useHistoryEntries, {DEFAULT_HISTORY_DAYS} from './useHistoryEntries';
import {fakeApi, NETWORK_ERROR} from '../../test/fakeApi';
import {SERVER_UNREACHABLE} from '../../api/client';

// Display order, as /api/factions/summary returns it.
const FACTIONS = [
    {name: 'Federation', color: '#0080ff', on_chart: true},
    {name: 'Romulan', color: 'rgb(0, 160, 0)', on_chart: true},
    {name: 'Klingon', color: null, on_chart: false},
    {name: 'Augment', color: '#ff0000', on_chart: true},
];

const ENTRIES = [
    {id: 1, faction_code: 'FED', faction_name: 'Federation', timestamp: '2026-11-17T10:00:00+00:00', value: 100},
    {id: 2, faction_code: 'KLI', faction_name: 'Klingon', timestamp: '2026-11-17T10:00:00+00:00', value: 50},
    {id: 3, faction_code: 'FED', faction_name: 'Federation', timestamp: '2026-11-17T11:00:00+00:00', value: 140},
    {id: 4, faction_code: 'AUG', faction_name: 'Augment', timestamp: '2026-11-17T11:00:00+00:00', value: 0},
];

const byLabel = (result) => Object.fromEntries(result.current.chartData.datasets.map(d => [d.label, d]));

describe('reload', () => {
    it('builds one series per faction, in display order', async () => {
        fakeApi(() => ({status: 200, data: ENTRIES}));
        const {result} = renderHook(() => useHistoryEntries());

        await act(() => result.current.reload(FACTIONS));

        expect(result.current.chartData.datasets.map(d => d.label))
            .toEqual(['Federation', 'Romulan', 'Klingon', 'Augment']);
        const series = byLabel(result);
        expect(series.Federation.data).toEqual([
            {x: new Date('2026-11-17T10:00:00+00:00'), y: 100},
            {x: new Date('2026-11-17T11:00:00+00:00'), y: 140},
        ]);
        expect(series.Federation.backgroundColor).toBe('rgba(0, 128, 255, 0.2)');
        expect(series.Romulan.backgroundColor).toBe('rgba(0, 160, 0, 0.2)');
        expect(series.Klingon.borderColor).toBe('rgb(128, 128, 128)');
    });

    it('starts a series hidden when On Chart is off or it has nothing to draw', async () => {
        fakeApi(() => ({status: 200, data: ENTRIES}));
        const {result} = renderHook(() => useHistoryEntries());

        await act(() => result.current.reload(FACTIONS));

        const series = byLabel(result);
        expect(series.Federation.hidden).toBe(false);
        expect(series.Klingon.hidden).toBe(true);   // On Chart off, though it has data
        expect(series.Romulan.hidden).toBe(true);   // no entries
        expect(series.Augment.hidden).toBe(true);   // only zeros
    });

    it('asks for the default window, then the whole history when toggled', async () => {
        const requests = fakeApi(() => ({status: 200, data: []}));
        const {result} = renderHook(() => useHistoryEntries());

        await act(() => result.current.reload(FACTIONS));
        expect(requests[0].params).toEqual({days: DEFAULT_HISTORY_DAYS});

        await act(async () => result.current.toggleFullHistory(FACTIONS));
        expect(result.current.historyDays).toBe(null);
        expect(requests[1].params).toEqual({});

        await act(async () => result.current.toggleFullHistory(FACTIONS));
        expect(result.current.historyDays).toBe(DEFAULT_HISTORY_DAYS);
        expect(requests[2].params).toEqual({days: DEFAULT_HISTORY_DAYS});
    });

    it('tells the user when the history could not be loaded', async () => {
        fakeApi(() => NETWORK_ERROR);
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
        vi.spyOn(console, 'error').mockImplementation(() => {});
        const {result} = renderHook(() => useHistoryEntries());

        await act(() => result.current.reload(FACTIONS));

        expect(alertSpy).toHaveBeenCalledWith(`Could not load reputation history: ${SERVER_UNREACHABLE}`);
        expect(result.current.chartData.datasets).toEqual([]);
    });
});

describe('visibility overrides', () => {
    it("keeps the user's legend choice across reloads", async () => {
        fakeApi(() => ({status: 200, data: ENTRIES}));
        const {result} = renderHook(() => useHistoryEntries());
        await act(() => result.current.reload(FACTIONS));

        act(() => result.current.toggleVisibility('Klingon', true));
        await act(() => result.current.reload(FACTIONS));

        // It was hidden; the click shows it.
        expect(result.current.hiddenOverrides).toEqual({Klingon: false});
    });
});
