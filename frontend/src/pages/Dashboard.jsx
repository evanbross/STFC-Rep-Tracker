/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
import React, {useEffect, useState} from 'react';
import { api, errorMessage } from '../api/client';
import ContextMenu, {useContextMenu} from '../components/ContextMenu';
import {useCaptureBusy} from '../hooks/useCaptureBusy';
import HistoryChart, {useHistoryEntries} from '../components/HistoryChart';
import TerritoryScheduleModal from '../components/TerritoryScheduleModal';

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

const Dashboard = () => {
    const [factions, setFactions] = useState([]);
    const [selectedFaction, setSelectedFaction] = useState(null);
    const history = useHistoryEntries(); // ai: claude-opus-5-5 | 2026-11-06
    const [isCapturing, setIsCapturing] = useState(false);
    const [capturingFactionId, setCapturingFactionId] = useState(null);
    // ai: claude-opus-5-5 | 2026-11-06 — also true while a capture started on another page runs
    const captureBusy = useCaptureBusy();
    const anyCaptureRunning = isCapturing || capturingFactionId !== null || captureBusy;
    const [showTerritorySchedule, setShowTerritorySchedule] = useState(false);
    const [cardsCollapsed, setCardsCollapsed] = useState(false);
    const awayTeamMenu = useContextMenu(); // ai: claude-opus-5-5 | 2026-10-17

    // ai: claude-opus-5-5 | 2026-11-06
    // Cards first, then the chart: the chart takes its colors and legend from
    // the same summary fetch. Falls back to the current list if that fetch failed.
    const refreshAll = async () => {
        const list = await loadFactions();
        await history.reload(list ?? factions);
    };

    useEffect(() => {
        refreshAll();
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
            await refreshAll();
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
                    await refreshAll();
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
                    await refreshAll();
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

            <HistoryChart history={history} factions={factions}/>
        </div>
    );
};

export default Dashboard;
