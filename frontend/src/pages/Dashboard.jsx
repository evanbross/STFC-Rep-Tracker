/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// Composes the Dashboard sections. Each section's state and API calls live in
// its own component folder; this page only owns the reload order between them.
import {useEffect, useEffectEvent, useState} from 'react';
import CaptureToolbar, {useCaptures} from '../components/CaptureToolbar';
import CommunityModStatus from '../components/CommunityModStatus'; // ai: claude-opus-5-5 | 2026-11-19
import FactionCards, {useFactionSummaries} from '../components/FactionCards';
import HistoryChart, {useHistoryEntries} from '../components/HistoryChart';
import SpocksClubImport from '../components/SpocksClubImport'; // ai: claude-opus-5-5 | 2026-11-17
import TerritoryScheduleModal from '../components/TerritoryScheduleModal';

const Dashboard = () => {
    const {factions, reload: reloadFactions, addEntry} = useFactionSummaries();
    const history = useHistoryEntries();
    const [showTerritorySchedule, setShowTerritorySchedule] = useState(false);

    // Cards first, then the chart: the chart takes its colors and legend from
    // the same summary fetch. Falls back to the current list if that fetch failed.
    const refreshAll = async () => {
        const list = await reloadFactions();
        await history.reload(list ?? factions);
    };

    const captures = useCaptures({onSaved: refreshAll});

    // ai: claude-opus-5-5 | 2026-11-18
    // The initial load runs once on mount. useEffectEvent lets it call the
    // latest refreshAll without making the effect re-run each time refreshAll
    // is recreated (every render), which would reload in a loop.
    const loadOnMount = useEffectEvent(() => {
        refreshAll();
    });
    useEffect(() => {
        loadOnMount();
    }, []);

    const submitEntry = async (factionName, value) => {
        const saved = await addEntry(factionName, value);
        if (saved) await refreshAll();
        return saved;
    };

    return (
        <div className="dashboard">
            {/* ai: claude-opus-5-5 | 2026-11-19 — title left, mod sync time top right; a sync that changed values reloads cards and chart */}
            <div className="dashboard-header">
                <h1>STFC Reputation Tracker</h1>
                <CommunityModStatus onReadingsSaved={refreshAll}/>
            </div>

            <div className="container">
                <FactionCards
                    factions={factions}
                    onSubmitEntry={submitEntry}
                    onCaptureFaction={captures.captureFaction}
                    capturingFactionCode={captures.capturingFactionCode}
                    captureDisabled={captures.anyCaptureRunning}
                />

                <CaptureToolbar
                    onCapture={captures.captureScreen}
                    disabled={captures.anyCaptureRunning}
                    onOpenSchedule={() => setShowTerritorySchedule(true)}
                />

                {/* ai: claude-opus-5-5 | 2026-11-17 — reads every faction at once from an export, no game automation */}
                <div style={{marginTop: '1rem'}}>
                    <SpocksClubImport onSaved={refreshAll}/>
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
