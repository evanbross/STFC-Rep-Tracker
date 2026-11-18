/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// Faction summaries and quick manual entries, moved out of Dashboard.jsx.
import {useState} from 'react';
import {api, errorMessage} from '../../api/client';

const byDisplayOrder = (a, b) => {
    const aOrder = typeof a.display_order === 'number' ? a.display_order : Number.MAX_SAFE_INTEGER;
    const bOrder = typeof b.display_order === 'number' ? b.display_order : Number.MAX_SAFE_INTEGER;
    if (aOrder !== bOrder) return aOrder - bOrder;
    return (a.name || '').localeCompare(b.name || '');
};

/**
 * Returns {factions, reload, addEntry}.
 *
 * reload() resolves to the fresh list, or null if the fetch failed (after
 * telling the user), so a caller can chain the chart reload off one fetch.
 * addEntry(name, value) resolves to true once the entry is saved.
 */
const useFactionSummaries = () => {
    const [factions, setFactions] = useState([]);

    const reload = async () => {
        try {
            const response = await api.get('/api/factions/summary?sort=display_order');
            const factionList = [...response.data].sort(byDisplayOrder);
            setFactions(factionList);
            return factionList;
        } catch (error) {
            console.error('Error loading factions:', error);
            window.alert(`Could not load factions: ${errorMessage(error)}`);
            return null;
        }
    };

    const addEntry = async (factionName, value) => {
        const parsed = parseInt(value, 10);
        if (!Number.isFinite(parsed)) {
            window.alert('Enter a valid number.');
            return false;
        }
        try {
            await api.post('/api/status_entries/', {faction: factionName, value: parsed});
            return true;
        } catch (error) {
            console.error('Error adding entry:', error);
            window.alert(`Failed to add entry: ${errorMessage(error)}`);
            return false;
        }
    };

    return {factions, reload, addEntry};
};

export default useFactionSummaries;
