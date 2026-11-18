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
import useSpocksClubImport, {toLocalInputValue} from './useSpocksClubImport';
import {fakeApi, jsonBody} from '../../test/fakeApi';

// Milliseconds on purpose: the datetime-local input drops them, and an
// unchanged time must still be sent back exactly.
const EXPORTED_AT = '2026-11-17T21:04:05.678+00:00';

const PREVIEW = {
    exported_at: EXPORTED_AT,
    exported_at_source: 'filename',
    readings: [
        {faction_code: 'FED', faction_name: 'Federation', resource_id: 970475396, value: 1200,
            previous_value: 1000, previous_updated: '2026-11-16T10:00:00+00:00'},
        {faction_code: 'ROM', faction_name: 'Romulan', resource_id: 970475397, value: 300,
            previous_value: null, previous_updated: null},
    ],
    unmatched: [],
};

const EXPORT_FILE = new File(['tsv'], 'export.tsv', {lastModified: 1_763_400_000_000});

let alertSpy;
beforeEach(() => {
    alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
});

const lastAlert = () => alertSpy.mock.calls.at(-1)[0];

/** A fake backend: /preview returns PREVIEW, /import returns `importReply`. */
const fakeBackend = (importReply) => fakeApi(({url}) => (
    url === '/api/spocks-club/preview' ? {status: 200, data: PREVIEW} : importReply
));

/** Render the hook and load PREVIEW through chooseFile. */
const renderWithPreview = async (onSaved) => {
    const hook = renderHook(() => useSpocksClubImport({onSaved}));
    await act(() => hook.result.current.chooseFile(EXPORT_FILE));
    return hook;
};

describe('chooseFile', () => {
    it("uploads the file with its modified time and shows the export's time", async () => {
        const requests = fakeBackend(null);
        const {result} = await renderWithPreview(vi.fn());

        const form = requests[0].data;
        expect(form).toBeInstanceOf(FormData);
        expect(form.get('file').name).toBe('export.tsv');
        expect(form.get('last_modified')).toBe('1763400000000');
        expect(result.current.preview).toEqual(PREVIEW);
        expect(result.current.timeInput).toBe(toLocalInputValue(EXPORTED_AT));
        expect(result.current.busy).toBe(false);
    });

    it("shows the backend's reason when the file can't be read", async () => {
        fakeApi(() => ({status: 400, data: {error: "That file isn't a text export."}}));
        const {result} = renderHook(() => useSpocksClubImport({onSaved: vi.fn()}));

        await act(() => result.current.chooseFile(EXPORT_FILE));

        expect(lastAlert()).toBe("Error: That file isn't a text export.");
        expect(result.current.preview).toBe(null);
    });
});

describe('confirmImport', () => {
    it('sends the exact export instant when the time was left alone', async () => {
        const requests = fakeBackend({status: 201, data: {saved: [{}, {}], skipped: []}});
        const onSaved = vi.fn();
        const {result} = await renderWithPreview(onSaved);

        await act(() => result.current.confirmImport());

        expect(jsonBody(requests[1])).toEqual({
            exported_at: EXPORTED_AT,
            readings: [{faction_code: 'FED', value: 1200}, {faction_code: 'ROM', value: 300}],
        });
        expect(onSaved).toHaveBeenCalledOnce();
        expect(result.current.preview).toBe(null);
        expect(lastAlert()).toBe('Imported 2 reading(s).');
    });

    it('sends the edited time as UTC', async () => {
        const requests = fakeBackend({status: 201, data: {saved: [{}], skipped: []}});
        const {result} = await renderWithPreview(vi.fn());

        act(() => result.current.setTimeInput('2026-11-15T08:30:00'));
        await act(() => result.current.confirmImport());

        expect(jsonBody(requests[1]).exported_at).toBe(new Date('2026-11-15T08:30:00').toISOString());
    });

    it('refuses an empty time without sending anything', async () => {
        const requests = fakeBackend(null);
        const {result} = await renderWithPreview(vi.fn());

        act(() => result.current.setTimeInput(''));
        await act(() => result.current.confirmImport());

        expect(requests).toHaveLength(1);
        expect(lastAlert()).toBe('Enter a valid date and time for these readings.');
        expect(result.current.preview).toEqual(PREVIEW);
    });

    it("lists skipped factions and doesn't reload when nothing new was saved", async () => {
        fakeBackend({status: 201, data: {saved: [], skipped: ['FED', 'ROM']}});
        const onSaved = vi.fn();
        const {result} = await renderWithPreview(onSaved);

        await act(() => result.current.confirmImport());

        expect(onSaved).not.toHaveBeenCalled();
        expect(lastAlert()).toBe('Imported 0 reading(s).\nAlready had a reading at that time (skipped): FED, ROM');
    });

    it('keeps the preview open when the import fails', async () => {
        fakeBackend({status: 404, data: {error: "Faction 'XYZ' not found"}});
        const {result} = await renderWithPreview(vi.fn());

        await act(() => result.current.confirmImport());

        expect(lastAlert()).toBe("Error: Faction 'XYZ' not found");
        expect(result.current.preview).toEqual(PREVIEW);
        expect(result.current.busy).toBe(false);
    });
});
