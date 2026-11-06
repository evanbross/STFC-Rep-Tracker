/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
import React, {useEffect, useRef, useState} from 'react';
import { api, errorMessage } from '../api/client';
import {
    CategoryScale,
    Chart as ChartJS,
    Legend,
    LinearScale,
    LineElement,
    PointElement,
    TimeScale,
    Title,
    Tooltip
} from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';
import {Line} from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import ContextMenu, {useContextMenu} from '../components/ContextMenu';
import {useCaptureBusy} from '../hooks/useCaptureBusy';
import TerritoryScheduleModal from '../components/TerritoryScheduleModal';

ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    TimeScale,
    annotationPlugin
);

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

const formatShort = (value, decimals = 0) => {
    if (value == null) return null;
    const sign = value < 0 ? '-' : '';
    const abs = Math.abs(value);
    const fmt = (n) => decimals > 0 ? n.toFixed(decimals) : String(Math.floor(n));
    if (abs >= 1_000_000_000) return `${sign}${fmt(abs / 1_000_000_000)}b`;
    if (abs >= 1_000_000) return `${sign}${fmt(abs / 1_000_000)}m`;
    if (abs >= 1_000) return `${sign}${fmt(abs / 1_000)}k`;
    return `${sign}${abs}`;
};

const formatMinutes = (minutes) => {
    const m = Math.round(minutes || 0);
    if (!m) return "0";
    const d = Math.floor(m / 1440);
    const h = Math.floor((m % 1440) / 60);
    const mins = m % 60;
    if (d > 0) return `${d}d ${h}h ${mins}m`;
    if (h > 0) return `${h}h ${mins}m`;
    return `${mins}m`;
};

// ai: claude-opus-5-5 | 2026-11-06 — the chart's default history window (N-P3)
const DEFAULT_HISTORY_DAYS = 30;

const Dashboard = () => {
    const [factions, setFactions] = useState([]);
    const [selectedFaction, setSelectedFaction] = useState(null);
    const [chartData, setChartData] = useState({datasets: []});
    // ai: claude-opus-5-5 | 2026-11-06 — null means the whole history
    const [historyDays, setHistoryDays] = useState(DEFAULT_HISTORY_DAYS);
    const [isCapturing, setIsCapturing] = useState(false);
    const [capturingFactionId, setCapturingFactionId] = useState(null);
    // ai: claude-opus-5-5 | 2026-11-06 — also true while a capture started on another page runs
    const captureBusy = useCaptureBusy();
    const anyCaptureRunning = isCapturing || capturingFactionId !== null || captureBusy;
    const [hiddenDatasets, setHiddenDatasets] = useState({});
    const [showTerritorySchedule, setShowTerritorySchedule] = useState(false);
    const [cardsCollapsed, setCardsCollapsed] = useState(false);
    const awayTeamMenu = useContextMenu(); // ai: claude-opus-5-5 | 2026-10-17
    const chartRef = useRef(null);

    useEffect(() => {
        loadFactions().then(list => loadEntries(list));
    }, []);

    const loadFactions = async () => {
        try {
            const response = await api.get('/api/factions/summary?sort=display_order');
            let factionList = response.data;

            factionList.sort((a, b) => {
                const aOrder = typeof a.display_order === 'number' ? a.display_order : Number.MAX_SAFE_INTEGER;
                const bOrder = typeof b.display_order === 'number' ? b.display_order : Number.MAX_SAFE_INTEGER;

                if (aOrder !== bOrder) return aOrder - bOrder;
                return (a.name || '').localeCompare(b.name || '');
            });

            setFactions(factionList);
            return factionList;
        } catch (error) {
            console.error('Error loading factions:', error);
            if (!error.response) {
                alert('Cannot reach the server. Is the backend running?');
            }
        }
    };

    // ai: claude-opus-5-5 | 2026-11-06
    // Colors come from the faction list passed in, not from state, so one
    // fetch is enough (N-P3); `days` limits the history to a recent window.
    const loadEntries = async (factionList, days = historyDays) => {
        try {
            const params = days ? {days} : {};
            const response = await api.get('/api/status_entries/all', {params});
            const grouped = {};
            const colors = {};
            // Seed all on_chart factions so they appear in the legend even with no data
            const list = factionList ?? factions;
            for (const f of list) {
                if (f.on_chart) grouped[f.name] = [];
                if (f.color) colors[f.name] = f.color;
            }
            for (const entry of response.data) {
                if (!grouped[entry.faction_name]) grouped[entry.faction_name] = [];
                grouped[entry.faction_name].push(entry);
            }
            updateChart(grouped, colors);
        } catch (error) {
            console.error('Error loading entries:', error);
            if (!error.response) {
                alert('Cannot reach the server. Is the backend running?');
            }
        }
    };

    const updateChart = (data, colors) => {
        const datasets = [];
        for (const [factionName, entries] of Object.entries(data)) {
            const hasData = entries.length > 0 && entries.some(e => e.value !== 0);
            {
                const color = colors[factionName] || 'rgb(128, 128, 128)'; // ai: claude-opus-5-5 | 2026-11-06

                const backgroundColor = colorToRgba(color, 0.2);

                datasets.push({
                    label: factionName,
                    data: entries.map(entry => ({
                        x: new Date(entry.timestamp),
                        y: entry.value
                    })),
                    borderColor: color,
                    backgroundColor: backgroundColor,
                    tension: 0.1,
                    fill: false,
                    hidden: !hasData
                });
            }
        }
        setChartData({datasets});
        setHiddenDatasets({});
    };

    // ai: claude-opus-5-5 | 2026-11-06
    const toggleFullHistory = () => {
        const nextDays = historyDays ? null : DEFAULT_HISTORY_DAYS;
        setHistoryDays(nextDays);
        loadEntries(factions, nextDays);
    };


    const submitEntry = async (factionName, value) => {
        const parsed = parseInt(value, 10);
        if (!Number.isFinite(parsed)) {
            alert('Enter a valid number.');
            return false;
        }
        try {
            await api.post('/api/status_entries/', {
                faction: factionName,
                value: parsed
            });
            const list = await loadFactions();
            await loadEntries(list);
            return true;
        } catch (error) {
            console.error('Error adding entry:', error);
            if (!error.response) {
                alert('Cannot reach the server. Is the backend running?');
            } else {
                alert('Failed to add entry.');
            }
            return false;
        }
    };

    const handleCaptureScreen = async (screen) => {
        const urlMap = {
            reputations: '/api/capture-screen/reputations',
            away_team_collect: '/api/capture-screen/away-team-collect',
            away_team: '/api/capture-screen/away-team',
            gifts: '/api/capture-screen/gifts',
        };
        setIsCapturing(true);
        try {
            const response = await api.post(urlMap[screen] ?? '/api/capture-screen/reputations');
            const data = response.data;

            if (data.error) {
                alert(`Error: ${data.error}`);
            } else if (data.saved && Array.isArray(data.saved)) {
                // Full faction sweep — entries already saved automatically
                const count = data.saved.length;
                if (count > 0) {
                    const list = await loadFactions();
                    await loadEntries(list);
                    const summary = data.saved
                        .map(s => `${s.faction}: ${s.points.toLocaleString()}`)
                        .join('\n');
                    alert(`Saved ${count} faction(s):\n${summary}`);
                } else {
                    alert('Scan complete — no reputation values could be read.');
                }
            } else if (data.reports_clicked !== undefined) {
                // Away team result
                // ai: claude-opus-5-5 | 2026-10-17
                alert(screen === 'away_team_collect'
                    ? `Away Team collect complete.\nReports collected: ${data.collected}`
                    : `Away Team complete.\n` +
                      `Reports collected: ${data.collected}\n` +
                      `Expeditions started: ${data.expeditions_started}`
                );
            } else if (data.success && data.claims !== undefined) {
                // Gifts result
                alert(`Gifts complete.\nClaim All clicked: ${data.claims}`);
            } else if (data.success) {
                alert('Done.');
            } else {
                alert('Capture returned an unexpected response.');
            }
        } catch (error) {
            console.error('Error capturing screen:', error);
            if (!error.response) {
                alert('Cannot reach the server. Is the backend running?');
            } else {
                alert(`Error: ${error.response.data?.error ?? 'Failed to capture screen.'}`);
            }
        } finally {
            setIsCapturing(false);
        }
    };

    const handleCaptureSingleFaction = async (faction) => {
        setCapturingFactionId(faction.id);
        try {
            const response = await api.post(`/api/capture-screen/reputations/${faction.id}`);
            const data = response.data;
            if (data.error) {
                alert(`Error: ${data.error}`);
            } else if (data.saved && Array.isArray(data.saved)) {
                if (data.saved.length > 0) {
                    const list = await loadFactions();
                    await loadEntries(list);
                } else {
                    alert(`${faction.name}: no reputation value could be read.`);
                }
            } else {
                alert('Capture returned an unexpected response.');
            }
        } catch (error) {
            console.error('Error capturing faction:', error);
            if (!error.response) {
                alert('Cannot reach the server. Is the backend running?');
            } else {
                alert(`Error: ${error.response.data?.error ?? `Failed to capture ${faction.name}.`}`);
            }
        } finally {
            setCapturingFactionId(null);
        }
    };


    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            x: {
                type: 'time',
                time: {
                    minUnit: 'minute',
                    displayFormats: {
                        minute: 'MMM d, HH:mm',
                        hour:   'MMM d, HH:mm',
                        day:    'MMM d',
                        week:   'MMM d',
                        month:  'MMM yyyy',
                    }
                },
                title: {
                    display: true,
                    text: 'Time'
                }
            },
            y: {
                title: {
                    display: true,
                    text: 'Reputation Value'
                }
            }
        },
        plugins: {
            legend: {
                display: false,
            },
            tooltip: {
                mode: 'index',
                intersect: false
            },
            annotation: {
                annotations: {
                    tenMillion: {
                        type: 'line',
                        yMin: 10000000,
                        yMax: 10000000,
                        borderColor: 'rgba(255, 255, 255, 0.6)',
                        borderWidth: 3,
                        label: {
                            display: true,
                            content: '10M',
                            position: 'end',
                            color: 'rgba(255, 255, 255, 0.8)',
                            font: {size: 11}
                        }
                    }
                }
            }
        }
    };

    return (
        <div className="dashboard">
            <h1>STFC Reputation Tracker</h1>

            <div className="container">
                <h2
                    style={{cursor: 'pointer', userSelect: 'none', display: 'flex', alignItems: 'center', gap: '0.5rem'}}
                    onClick={() => setCardsCollapsed(c => !c)}
                >
                    <span style={{fontSize: '0.8em', color: '#888'}}>{cardsCollapsed ? '▶' : '▼'}</span>
                    Faction Summaries
                </h2>
                <div className="form-group" style={cardsCollapsed ? {display: 'none'} : {}}>
                    <div className="faction-buttons">
                        {factions.map(faction => {
                            const isSelected = selectedFaction?.name === faction.name;
                            let factionNameStyle = faction.color ? {color: faction.color} : {};
                            if (['gold', 'silver', 'orange'].includes(faction.color)) {
                                factionNameStyle = {
                                    ...factionNameStyle,
                                    WebkitTextStroke: '0.5px black',
                                    textShadow: '0 0 1px black'
                                };
                            }

                            const progressPct = faction.status?.goal_value
                                ? Math.min(100, Math.max(0, (faction.current_value / faction.status.goal_value) * 100))
                                : 0;
                            return (
                                <div
                                    key={faction.name}
                                    className={`faction-btn ${isSelected ? 'selected' : ''}`}
                                    style={isSelected && faction.color ? {
                                        borderColor: faction.color,
                                        backgroundColor: faction.color + '1a'
                                    } : {}}
                                    onClick={() => setSelectedFaction(faction)}
                                >
                                    <div className="faction-content">
                                        <div className="faction-header">
                                            <span className="faction-name" style={factionNameStyle}>{faction.name}</span>
                                            {faction.rep_level && (
                                                <span
                                                    className="faction-rep-badge"
                                                    style={faction.color ? {borderColor: faction.color + '55', color: faction.color} : {}}
                                                >{faction.rep_level}</span>
                                            )}
                                        </div>
                                        <div className="faction-value-row">
                                            <span className="faction-value">{formatShort(faction.current_value, 1)}</span>
                                            {faction.last_delta != null && (
                                                <span className={`faction-delta ${faction.last_delta > 0 ? 'pos' : faction.last_delta < 0 ? 'neg' : 'zero'}`}>
                                                    {faction.last_delta >= 0 ? '+' : ''}{formatShort(faction.last_delta, 1)}
                                                </span>
                                            )}
                                        </div>
                                        <div className="faction-stats">
                                            <span className="stat-label">Rate</span>
                                            <span className="stat-value">{Math.round(faction.status?.raw_value_delta_per_minute || 0)}/min</span>
                                            <span className="stat-label">Avg</span>
                                            <span className="stat-value">{Math.round(faction.status?.avg_value_delta_per_minute || 0)}/min</span>
                                            {faction.status?.minutes_to_goal != null && (
                                                <span className="stat-goal">
                                                    → {faction.status.next_rep_level || 'Goal'}
                                                    {faction.status.goal_value ? ` (${formatShort(faction.status.goal_value, 1)})` : ''}: {formatMinutes(faction.status.minutes_to_goal)}
                                                </span>
                                            )}
                                        </div>
                                        <div className="quick-edit" onClick={e => e.stopPropagation()}>
                                            <input
                                                type="number"
                                                className="quick-edit-input"
                                                placeholder="New value"
                                                onKeyDown={e => {
                                                    if (e.key === 'Enter') {
                                                        const input = e.target;
                                                        submitEntry(faction.name, input.value).then(success => {
                                                            if (success) input.value = '';
                                                        });
                                                    }
                                                }}
                                            />
                                            <button
                                                className="quick-edit-btn"
                                                onClick={e => {
                                                    const input = e.currentTarget.previousElementSibling;
                                                    submitEntry(faction.name, input.value).then(success => {
                                                        if (success) input.value = '';
                                                    });
                                                }}
                                            >
                                                Save
                                            </button>
                                        </div>
                                        <div className="quick-edit" onClick={e => e.stopPropagation()}>
                                            <button
                                                className="quick-edit-btn"
                                                style={{width: '100%'}}
                                                disabled={anyCaptureRunning}
                                                onClick={() => handleCaptureSingleFaction(faction)}
                                            >
                                                {capturingFactionId === faction.id ? 'Capturing…' : 'Capture'}
                                            </button>
                                        </div>
                                    </div>
                                    <div className="faction-progress">
                                        <div
                                            className="faction-progress-fill"
                                            style={{
                                                width: `${progressPct}%`,
                                                backgroundColor: faction.color || 'var(--c-accent)',
                                            }}
                                        />
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                <h2 style={{marginTop: '2rem'}}>Auto Capture</h2>
                <p style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
                    Click a button below to automatically locate Star Trek Fleet Command,
                    switch to the selected screen, and take a screenshot for processing.
                </p>
                <div style={{display: 'flex', gap: '0.75rem'}}>
                    <button className="btn-capture" onClick={() => handleCaptureScreen('reputations')} disabled={anyCaptureRunning}>
                        Reputations
                    </button>
                    {/* ai: claude-opus-5-5 | 2026-10-17 — right-click opens collect-only option */}
                    <button
                        className="btn-capture"
                        onClick={() => handleCaptureScreen('away_team')}
                        {...awayTeamMenu.bind(!anyCaptureRunning)}
                        disabled={anyCaptureRunning}
                        title="Click: collect + start new missions. Right-click for more options."
                    >
                        Away Team
                    </button>
                    <ContextMenu
                        position={awayTeamMenu.position}
                        onClose={awayTeamMenu.close}
                        items={[
                            {label: 'Collect + start new missions', onSelect: () => handleCaptureScreen('away_team')},
                            {label: 'Collect only', onSelect: () => handleCaptureScreen('away_team_collect')},
                        ]}
                    />
                    <button className="btn-capture" onClick={() => handleCaptureScreen('gifts')} disabled={anyCaptureRunning}>
                        Gifts
                    </button>
                    <button className="btn-capture" disabled={true} title="Not implemented yet">
                        Event Rewards
                    </button>
                    <button className="btn-outline" onClick={() => setShowTerritorySchedule(true)}>
                        TC Schedule
                    </button>
                </div>

                {showTerritorySchedule && (
                    <TerritoryScheduleModal onClose={() => setShowTerritorySchedule(false)}/>
                )}
            </div>

            <div className="chart-container">
                <div style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '0.4rem 1rem',
                    padding: '0.5rem 0.75rem',
                    marginBottom: '0.5rem'
                }}>
                    {chartData.datasets.map((ds, i) => {
                        const isHidden = hiddenDatasets[i] ?? ds.hidden;
                        return (
                            <div
                                key={ds.label}
                                onClick={() => {
                                    const chart = chartRef.current;
                                    if (!chart) return;
                                    const next = !isHidden;
                                    chart.setDatasetVisibility(i, !next);
                                    chart.update();
                                    setHiddenDatasets(prev => ({...prev, [i]: next}));
                                }}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: '0.4rem',
                                    cursor: 'pointer', opacity: isHidden ? 0.4 : 1,
                                    fontSize: '0.8rem', userSelect: 'none'
                                }}
                            >
                                <span style={{
                                    display: 'inline-block', width: 12, height: 12,
                                    borderRadius: 2, flexShrink: 0,
                                    backgroundColor: isHidden ? 'transparent' : ds.borderColor,
                                    border: `2px solid ${ds.borderColor}`
                                }}/>
                                <span style={{textDecoration: isHidden ? 'line-through' : 'none'}}>
                                    {ds.label}
                                </span>
                            </div>
                        );
                    })}
                    {/* ai: claude-opus-5-5 | 2026-11-06 */}
                    <button
                        type="button"
                        onClick={toggleFullHistory}
                        style={{marginLeft: 'auto', fontSize: '0.8rem'}}
                        title={historyDays ? 'Load every entry ever recorded' : `Show only the last ${DEFAULT_HISTORY_DAYS} days`}
                    >
                        {historyDays ? 'Show all history' : `Last ${DEFAULT_HISTORY_DAYS} days`}
                    </button>
                </div>
                <Line ref={chartRef} options={chartOptions} data={chartData}/>
            </div>
        </div>
    );
};

export default Dashboard;
