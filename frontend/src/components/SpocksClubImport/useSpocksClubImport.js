/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-17
// State and requests for importing a Spock's Club export: upload -> preview -> confirm.
import {useState} from 'react';
import {api, errorMessage} from '../../api/client';

/** ISO instant -> the local "YYYY-MM-DDTHH:mm:ss" a datetime-local input shows. */
export const toLocalInputValue = (iso) => {
    const d = new Date(iso);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
        `T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
};

/**
 * Returns {preview, timeInput, setTimeInput, busy, chooseFile, confirmImport, cancel}.
 *
 * preview is the /preview response (null when closed). onSaved() runs after an
 * import that stored at least one reading, so the cards and chart can reload.
 */
const useSpocksClubImport = ({onSaved}) => {
    const [preview, setPreview] = useState(null);
    const [timeInput, setTimeInput] = useState('');
    const [busy, setBusy] = useState(false);

    const chooseFile = async (file) => {
        if (!file) return;
        const form = new FormData();
        form.append('file', file);
        // Used for the reading time when the filename has no export time in it.
        form.append('last_modified', String(file.lastModified));
        setBusy(true);
        try {
            const response = await api.post('/api/spocks-club/preview', form);
            setPreview(response.data);
            setTimeInput(toLocalInputValue(response.data.exported_at));
        } catch (error) {
            console.error("Error reading Spock's Club export:", error);
            window.alert(`Error: ${errorMessage(error, "Couldn't read that export.")}`);
        } finally {
            setBusy(false);
        }
    };

    const confirmImport = async () => {
        // Send the server's exact instant unless the user changed it: the input
        // drops milliseconds, and re-importing the same file relies on an exact
        // match to skip readings it already saved.
        const unchanged = timeInput === toLocalInputValue(preview.exported_at);
        const chosen = unchanged ? new Date(preview.exported_at) : new Date(timeInput);
        if (Number.isNaN(chosen.getTime())) {
            window.alert('Enter a valid date and time for these readings.');
            return;
        }
        setBusy(true);
        try {
            const response = await api.post('/api/spocks-club/import', {
                exported_at: unchanged ? preview.exported_at : chosen.toISOString(),
                readings: preview.readings.map(r => ({faction_code: r.faction_code, value: r.value})),
            });
            const {saved, skipped} = response.data;
            if (saved.length > 0) await onSaved();
            setPreview(null);
            const skippedNote = skipped.length
                ? `\nAlready had a reading at that time (skipped): ${skipped.join(', ')}`
                : '';
            window.alert(`Imported ${saved.length} reading(s).${skippedNote}`);
        } catch (error) {
            console.error("Error importing Spock's Club readings:", error);
            window.alert(`Error: ${errorMessage(error, 'Import failed.')}`);
        } finally {
            setBusy(false);
        }
    };

    const cancel = () => setPreview(null);

    return {preview, timeInput, setTimeInput, busy, chooseFile, confirmImport, cancel};
};

export default useSpocksClubImport;
