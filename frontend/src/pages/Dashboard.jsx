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
import FactionCards, {useFactionSummaries} from '../components/FactionCards';
import HistoryChart, {useHistoryEntries} from '../components/HistoryChart';
import TerritoryScheduleModal from '../components/TerritoryScheduleModal';

const Dashboard = () => {
    // ai: claude-opus-5-5 | 2026-11-06
    const {factions, reload: reloadFactions, addEntry} = useFactionSummaries();
    const history = useHistoryEntries();
    const [isCapturing, setIsCapturing] = useState(false);
    const [capturingFactionId, setCapturingFactionId] = useState(null);
    // ai: claude-opus-5-5 | 2026-11-06 — also true while a capture started on another page runs
    const captureBusy = useCaptureBusy();
    const anyCaptureRunning = isCapturing || capturingFactionId !== null || captureBusy;
    const [showTerritorySchedule, setShowTerritorySchedule] = useState(false);
    const awayTeamMenu = useContextMenu(); // ai: claude-opus-5-5 | 2026-10-17

    // ai: claude-opus-5-5 | 2026-11-06
    // Cards first, then the chart: the chart takes its colors and legend from
    // the same summary fetch. Falls back to the current list if that fetch failed.
    const refreshAll = async () => {
        const list = await reloadFactions();
        await history.reload(list ?? factions);
    };

    useEffect(() => {
        refreshAll();
    }, []);

    // ai: claude-opus-5-5 | 2026-11-06
    const submitEntry = async (factionName, value) => {
        const saved = await addEntry(factionName, value);
        if (saved) await refreshAll();
        return saved;
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
                <FactionCards
                    factions={factions}
                    onSubmitEntry={submitEntry}
                    onCaptureFaction={handleCaptureSingleFaction}
                    capturingFactionId={capturingFactionId}
                    captureDisabled={anyCaptureRunning}
                />

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
