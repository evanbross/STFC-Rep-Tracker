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
import React, {useEffect, useState} from 'react';
import CaptureToolbar, {useCaptures} from '../components/CaptureToolbar';
import FactionCards, {useFactionSummaries} from '../components/FactionCards';
import HistoryChart, {useHistoryEntries} from '../components/HistoryChart';
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

    useEffect(() => {
        refreshAll();
    }, []);

    const submitEntry = async (factionName, value) => {
        const saved = await addEntry(factionName, value);
        if (saved) await refreshAll();
        return saved;
    };

    return (
        <div className="dashboard">
            <h1>STFC Reputation Tracker</h1>

            <div className="container">
                <FactionCards
                    factions={factions}
                    onSubmitEntry={submitEntry}
                    onCaptureFaction={captures.captureFaction}
                    capturingFactionId={captures.capturingFactionId}
                    captureDisabled={captures.anyCaptureRunning}
                />

                <CaptureToolbar
                    onCapture={captures.captureScreen}
                    disabled={captures.anyCaptureRunning}
                    onOpenSchedule={() => setShowTerritorySchedule(true)}
                />

                {showTerritorySchedule && (
                    <TerritoryScheduleModal onClose={() => setShowTerritorySchedule(false)}/>
                )}
            </div>

            <HistoryChart history={history} factions={factions}/>
        </div>
    );
};

export default Dashboard;
