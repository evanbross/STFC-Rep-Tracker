/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// The Dashboard's "Auto Capture" button row, moved out of Dashboard.jsx.
import React from 'react';
import ContextMenu, {useContextMenu} from '../ContextMenu';

/**
 * onCapture(screen): a key of CAPTURE_URLS in useCaptures.
 * disabled: true while any capture runs.
 * onOpenSchedule(): opens the Territory Schedule modal (no capture involved).
 */
const CaptureToolbar = ({onCapture, disabled, onOpenSchedule}) => {
    const awayTeamMenu = useContextMenu(); // ai: claude-opus-5-5 | 2026-10-17

    return (
        <>
            <h2 style={{marginTop: '2rem'}}>Auto Capture</h2>
            <p style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
                Click a button below to automatically locate Star Trek Fleet Command,
                switch to the selected screen, and take a screenshot for processing.
            </p>
            <div style={{display: 'flex', gap: '0.75rem'}}>
                <button className="btn-capture" onClick={() => onCapture('reputations')} disabled={disabled}>
                    Reputations
                </button>
                {/* ai: claude-opus-5-5 | 2026-10-17 — right-click opens collect-only option */}
                <button
                    className="btn-capture"
                    onClick={() => onCapture('away_team')}
                    {...awayTeamMenu.bind(!disabled)}
                    disabled={disabled}
                    title="Click: collect + start new missions. Right-click for more options."
                >
                    Away Team
                </button>
                <ContextMenu
                    position={awayTeamMenu.position}
                    onClose={awayTeamMenu.close}
                    items={[
                        {label: 'Collect + start new missions', onSelect: () => onCapture('away_team')},
                        {label: 'Collect only', onSelect: () => onCapture('away_team_collect')},
                    ]}
                />
                <button className="btn-capture" onClick={() => onCapture('gifts')} disabled={disabled}>
                    Gifts
                </button>
                <button className="btn-capture" disabled={true} title="Not implemented yet">
                    Event Rewards
                </button>
                <button className="btn-outline" onClick={onOpenSchedule}>
                    TC Schedule
                </button>
            </div>
        </>
    );
};

export default CaptureToolbar;
