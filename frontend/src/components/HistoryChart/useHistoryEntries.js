/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// Status-entry history for the Dashboard chart, moved out of Dashboard.jsx.
import {useState} from 'react';
import {api, errorMessage} from '../../api/client';

// The chart's default history window (N-P3); null means the whole history.
export const DEFAULT_HISTORY_DAYS = 30;

const colorToRgba = (color, alpha) => {
    if (color.startsWith('#')) {
        const r = parseInt(color.slice(1, 3), 16);
        const g = parseInt(color.slice(3, 5), 16);
        const b = parseInt(color.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
    if (color.startsWith('rgb')) {
        return color.replace('rgb', 'rgba').replace(')', `, ${alpha})`);
    }
    return color;
};

/** One Chart.js dataset per faction; empty or all-zero series start hidden. */
const buildDatasets = (grouped, colors) => Object.entries(grouped).map(([factionName, entries]) => {
    const color = colors[factionName] || 'rgb(128, 128, 128)';
    return {
        label: factionName,
        data: entries.map(entry => ({x: new Date(entry.timestamp), y: entry.value})),
        borderColor: color,
        backgroundColor: colorToRgba(color, 0.2),
        tension: 0.1,
        fill: false,
        hidden: !(entries.length > 0 && entries.some(e => e.value !== 0)),
    };
});

/**
 * Returns {chartData, hiddenDatasets, setHiddenDatasets, historyDays, reload, toggleFullHistory}.
 *
 * reload(factions) takes the faction list instead of reading it from state,
 * so one summary fetch serves both the cards and the chart colors (N-P3).
 */
const useHistoryEntries = () => {
    const [chartData, setChartData] = useState({datasets: []});
    const [hiddenDatasets, setHiddenDatasets] = useState({});
    const [historyDays, setHistoryDays] = useState(DEFAULT_HISTORY_DAYS);

    const reload = async (factions, days = historyDays) => {
        try {
            const params = days ? {days} : {};
            const response = await api.get('/api/status_entries/all', {params});
            const grouped = {};
            const colors = {};
            // Seed all on_chart factions so they appear in the legend even with no data
            for (const f of factions) {
                if (f.on_chart) grouped[f.name] = [];
                if (f.color) colors[f.name] = f.color;
            }
            for (const entry of response.data) {
                if (!grouped[entry.faction_name]) grouped[entry.faction_name] = [];
                grouped[entry.faction_name].push(entry);
            }
            setChartData({datasets: buildDatasets(grouped, colors)});
            setHiddenDatasets({});
        } catch (error) {
            console.error('Error loading entries:', error);
            alert(`Could not load reputation history: ${errorMessage(error)}`);
        }
    };

    const toggleFullHistory = (factions) => {
        const nextDays = historyDays ? null : DEFAULT_HISTORY_DAYS;
        setHistoryDays(nextDays);
        reload(factions, nextDays);
    };

    return {chartData, hiddenDatasets, setHiddenDatasets, historyDays, reload, toggleFullHistory};
};

export default useHistoryEntries;
