/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// Collapsible faction summary cards (value, delta, rates, goal, quick entry,
// single-faction capture), moved out of Dashboard.jsx.
import {useState} from 'react';
import {formatMinutes, formatShort} from './format';

/**
 * factions: summary rows from useFactionSummaries.
 * onSubmitEntry(name, value): resolves true once saved; the input clears then.
 * onCaptureFaction(faction): runs a single-faction capture.
 * capturingFactionCode: code of the faction being captured, or null.
 * captureDisabled: true while any capture runs.
 */
const FactionCards = ({factions, onSubmitEntry, onCaptureFaction, capturingFactionCode, captureDisabled}) => {
    const [selectedFaction, setSelectedFaction] = useState(null);
    const [cardsCollapsed, setCardsCollapsed] = useState(false);

    return (
        <>
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

                        // ai: claude-opus-5-5 | 2026-11-07
                        const capped = faction.status?.capped === true;
                        const progressPct = capped ? 100 : faction.status?.goal_value
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
                                        {capped && ( // ai: claude-opus-5-5 | 2026-11-07
                                            <span className="stat-goal">Capped at {faction.rep_level}</span>
                                        )}
                                        {!capped && faction.status?.minutes_to_goal != null && (
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
                                                    onSubmitEntry(faction.name, input.value).then(success => {
                                                        if (success) input.value = '';
                                                    });
                                                }
                                            }}
                                        />
                                        <button
                                            className="quick-edit-btn"
                                            onClick={e => {
                                                const input = e.currentTarget.previousElementSibling;
                                                onSubmitEntry(faction.name, input.value).then(success => {
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
                                            disabled={captureDisabled}
                                            onClick={() => onCaptureFaction(faction)}
                                        >
                                            {capturingFactionCode === faction.code ? 'Capturing…' : 'Capture'}
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
        </>
    );
};

export default FactionCards;
