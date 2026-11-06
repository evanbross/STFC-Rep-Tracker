/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// Reputation history chart with its clickable legend, moved out of Dashboard.jsx.
import React, {useRef} from 'react';
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
import {DEFAULT_HISTORY_DAYS} from './useHistoryEntries';

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

const CHART_OPTIONS = {
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

/**
 * history: the object returned by useHistoryEntries (Dashboard owns it, since
 * captures and quick entries reload it).
 * factions: the current summary list, needed again when toggling the window.
 */
const HistoryChart = ({history, factions}) => {
    const {chartData, hiddenDatasets, setHiddenDatasets, historyDays, toggleFullHistory} = history;
    const chartRef = useRef(null);

    return (
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
                <button
                    type="button"
                    onClick={() => toggleFullHistory(factions)}
                    style={{marginLeft: 'auto', fontSize: '0.8rem'}}
                    title={historyDays ? 'Load every entry ever recorded' : `Show only the last ${DEFAULT_HISTORY_DAYS} days`}
                >
                    {historyDays ? 'Show all history' : `Last ${DEFAULT_HISTORY_DAYS} days`}
                </button>
            </div>
            <Line ref={chartRef} options={CHART_OPTIONS} data={chartData}/>
        </div>
    );
};

export default HistoryChart;
