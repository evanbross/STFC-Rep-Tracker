/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// The Dashboard's capture requests and their running state, moved out of Dashboard.jsx.
import {useState} from 'react';
import {api, errorMessage} from '../../api/client';
import {useCaptureBusy} from '../../hooks/useCaptureBusy';

export const CAPTURE_URLS = {
    reputations: '/api/capture-screen/reputations',
    away_team_collect: '/api/capture-screen/away-team-collect',
    away_team: '/api/capture-screen/away-team',
    gifts: '/api/capture-screen/gifts',
};

/** True when a reputation capture stored at least one value. */
const savedAny = (data) => Array.isArray(data.saved) && data.saved.length > 0;

/** The alert text for a successful capture, by what the response contains. */
const describeResult = (screen, data) => {
    if (Array.isArray(data.saved)) {
        if (data.saved.length === 0) return 'Scan complete — no reputation values could be read.';
        const summary = data.saved.map(s => `${s.faction}: ${s.points.toLocaleString()}`).join('\n');
        return `Saved ${data.saved.length} faction(s):\n${summary}`;
    }
    if (data.reports_clicked !== undefined) {
        return screen === 'away_team_collect'
            ? `Away Team collect complete.\nReports collected: ${data.collected}`
            : `Away Team complete.\n` +
              `Reports collected: ${data.collected}\n` +
              `Expeditions started: ${data.expeditions_started}`;
    }
    if (data.success && data.claims !== undefined) return `Gifts complete.\nClaim All clicked: ${data.claims}`;
    if (data.success) return 'Done.';
    return 'Capture returned an unexpected response.';
};

/**
 * Returns {isCapturing, capturingFactionCode, anyCaptureRunning, captureScreen, captureFaction}.
 *
 * onSaved() runs after any capture that stored reputation values, so the
 * cards and chart can reload. anyCaptureRunning also covers captures started
 * on other pages (useCaptureBusy), since the backend runs one at a time.
 */
const useCaptures = ({onSaved}) => {
    const [isCapturing, setIsCapturing] = useState(false);
    const [capturingFactionCode, setCapturingFactionCode] = useState(null);
    const captureBusy = useCaptureBusy();
    const anyCaptureRunning = isCapturing || capturingFactionCode !== null || captureBusy;

    const captureScreen = async (screen) => {
        const url = CAPTURE_URLS[screen];
        if (!url) throw new Error(`Unknown capture screen: ${screen}`);
        setIsCapturing(true);
        try {
            const response = await api.post(url);
            if (savedAny(response.data)) await onSaved();
            window.alert(describeResult(screen, response.data));
        } catch (error) {
            console.error('Error capturing screen:', error);
            window.alert(`Error: ${errorMessage(error, 'Failed to capture screen.')}`);
        } finally {
            setIsCapturing(false);
        }
    };

    const captureFaction = async (faction) => {
        setCapturingFactionCode(faction.code); // ai: claude-opus-5-5 | 2026-11-18
        try {
            const response = await api.post(`/api/capture-screen/reputations/${faction.code}`);
            if (savedAny(response.data)) {
                await onSaved();
            } else if (Array.isArray(response.data.saved)) {
                window.alert(`${faction.name}: no reputation value could be read.`);
            } else {
                window.alert('Capture returned an unexpected response.');
            }
        } catch (error) {
            console.error('Error capturing faction:', error);
            window.alert(`Error: ${errorMessage(error, `Failed to capture ${faction.name}.`)}`);
        } finally {
            setCapturingFactionCode(null);
        }
    };

    return {isCapturing, capturingFactionCode, anyCaptureRunning, captureScreen, captureFaction};
};

export default useCaptures;
