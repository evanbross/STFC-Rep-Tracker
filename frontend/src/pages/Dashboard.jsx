import React, {useEffect, useRef, useState} from 'react';
import axios from 'axios';
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
    const abs = Math.abs(value);
    const fmt = (n) => decimals > 0 ? n.toFixed(decimals) : String(Math.floor(n));
    if (abs >= 1_000_000_000) return `${fmt(abs / 1_000_000_000)}b`;
    if (abs >= 1_000_000) return `${fmt(abs / 1_000_000)}m`;
    if (abs >= 1_000) return `${fmt(abs / 1_000)}k`;
    return String(abs);
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
    const [chartData, setChartData] = useState({datasets: []});
    const [factionColorsMap, setFactionColorsMap] = useState({});
    const [isCapturing, setIsCapturing] = useState(false);
    const [capturingFactionId, setCapturingFactionId] = useState(null);
    const [hiddenDatasets, setHiddenDatasets] = useState({});
    const [territorySystems, setTerritorySystems] = useState(null);
    const [calendarAuthenticated, setCalendarAuthenticated] = useState(null);
    const chartRef = useRef(null);

    useEffect(() => {
        loadFactions().then(list => loadEntries(list));
        axios.get('/api/calendar/status')
            .then(r => setCalendarAuthenticated(r.data.authenticated))
            .catch(() => setCalendarAuthenticated(false));
    }, []);

    const loadFactions = async () => {
        try {
            const response = await axios.get('/api/factions/summary?sort=display_order');
            let factionList = response.data;

            factionList.sort((a, b) => {
                const aOrder = typeof a.display_order === 'number' ? a.display_order : Number.MAX_SAFE_INTEGER;
                const bOrder = typeof b.display_order === 'number' ? b.display_order : Number.MAX_SAFE_INTEGER;

                if (aOrder !== bOrder) return aOrder - bOrder;
                return (a.name || '').localeCompare(b.name || '');
            });

            const colors = {};
            factionList.forEach(f => {
                if (f.color) colors[f.name] = f.color;
            });
            setFactionColorsMap(colors);
            setFactions(factionList);
            return factionList;
        } catch (error) {
            console.error('Error loading factions:', error);
            if (!error.response) {
                alert('Cannot reach the server. Is the backend running?');
            }
        }
    };

    const loadEntries = async (factionList) => {
        try {
            const response = await axios.get('/api/status_entries/all');
            const grouped = {};
            // Seed all on_chart factions so they appear in the legend even with no data
            const list = factionList ?? factions;
            for (const f of list) {
                if (f.on_chart) grouped[f.name] = [];
            }
            for (const entry of response.data) {
                if (!grouped[entry.faction_name]) grouped[entry.faction_name] = [];
                grouped[entry.faction_name].push(entry);
            }
            updateChart(grouped);
        } catch (error) {
            console.error('Error loading entries:', error);
            if (!error.response) {
                alert('Cannot reach the server. Is the backend running?');
            }
        }
    };

    const updateChart = (data) => {
        const datasets = [];
        for (const [factionName, entries] of Object.entries(data)) {
            const hasData = entries.length > 0 && entries.some(e => e.value !== 0);
            {
                const color = factionColorsMap[factionName] || 'rgb(128, 128, 128)';

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

    // Re-update chart when factionColorsMap changes
    useEffect(() => {
        if (Object.keys(factionColorsMap).length > 0) {
            loadEntries(factions);
        }
    }, [factionColorsMap]);


    const submitEntry = async (factionName, value) => {
        try {
            await axios.post('/api/status_entries/', {
                faction: factionName,
                value: parseInt(value)
            });
            const list = await loadFactions();
            await loadEntries(list);
        } catch (error) {
            console.error('Error adding entry:', error);
            if (!error.response) {
                alert('Cannot reach the server. Is the backend running?');
            } else {
                alert('Failed to add entry.');
            }
        }
    };

    const handleCaptureScreen = async (screen) => {
        const urlMap = {
            reputations: '/api/capture-screen/reputations',
            away_team_collect: '/api/capture-screen/away-team-collect',
            away_team: '/api/capture-screen/away-team',
            gifts: '/api/capture-screen/gifts',
            event_rewards: '/api/capture-screen/event-rewards',
            territory_capture: '/api/capture-screen/territory-capture',
        };
        setIsCapturing(true);
        try {
            const response = await axios.post(urlMap[screen] ?? '/api/capture-screen/reputations');
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
                alert(
                    `Away Team complete.\n` +
                    `Reports collected: ${data.collected}\n` +
                    `Expeditions started: ${data.expeditions_started}`
                );
            } else if (data.success && data.claims !== undefined) {
                // Gifts result
                alert(`Gifts complete.\nClaim All clicked: ${data.claims}`);
            } else if (data.success && data.systems !== undefined) {
                // Territory capture result
                setTerritorySystems(data.systems);
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
                alert('Failed to capture screen.');
            }
        } finally {
            setIsCapturing(false);
        }
    };

    const handleConnectCalendar = async () => {
        try {
            await axios.post('/api/calendar/auth');
            setCalendarAuthenticated(true);
            alert('Google Calendar connected successfully.');
        } catch (error) {
            const msg = error.response?.data?.error || error.message || 'Unknown error';
            alert(`Google Calendar auth failed:\n\n${msg}`);
        }
    };

    const handleCaptureSingleFaction = async (faction) => {
        setCapturingFactionId(faction.id);
        try {
            const response = await axios.post(`/api/capture-screen/reputations/${faction.id}`);
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
                alert(`Failed to capture ${faction.name}.`);
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
                    unit: 'minute',
                    displayFormats: {
                        minute: 'MMM d, HH:mm'
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
                <h2>Faction Summaries</h2>
                <div className="form-group">
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
                                    <div className="faction-name" style={factionNameStyle}>{faction.name}</div>
                                    <div className="faction-rep-level">{faction.rep_level}</div>
                                    <div className="faction-status">
                                        <div className="status-item full-width">
                                            <span className="status-label">Value / Change:</span>
                                            <span className="status-value">
                                                {formatShort(faction.current_value, 3)} / {faction.last_delta >= 0 ? '+' : '-'}{formatShort(faction.last_delta, 3)}
                                            </span>
                                        </div>
                                        <div className="status-item full-width">
                                            <span className="status-label">Last Change Rate:</span>
                                            <span
                                                className="status-value">{Math.round(faction.status?.raw_value_delta_per_minute || 0)}/min</span>
                                        </div>
                                        <div className="status-item full-width">
                                            <span className="status-label">Avg Change Rate:</span>
                                            <span
                                                className="status-value">{Math.round(faction.status?.avg_value_delta_per_minute || 0)}/min</span>
                                        </div>
                                        <div className="status-item full-width">
                                            <span className="status-label">
                                                Time to {faction.status?.next_rep_level || 'Goal'}{formatShort(faction.status?.goal_value, 1) ? ` (${formatShort(faction.status?.goal_value, 1)})` : ''}:
                                            </span>
                                            <span
                                                className="status-value">{formatMinutes(faction.status?.minutes_to_goal)}</span>
                                        </div>
                                    </div>
                                    <div className="quick-edit" onClick={e => e.stopPropagation()}>
                                        <input
                                            type="number"
                                            className="quick-edit-input"
                                            placeholder="New Value"
                                            onKeyDown={e => {
                                                if (e.key === 'Enter') {
                                                    submitEntry(faction.name, e.target.value);
                                                    e.target.value = '';
                                                }
                                            }}
                                        />
                                        <button
                                            className="quick-edit-btn"
                                            onClick={e => {
                                                const input = e.currentTarget.previousElementSibling;
                                                submitEntry(faction.name, input.value);
                                                input.value = '';
                                            }}
                                        >
                                            Save
                                        </button>
                                    </div>
                                    <div className="quick-edit" onClick={e => e.stopPropagation()}>
                                        <button
                                            className="quick-edit-btn"
                                            style={{width: '100%'}}
                                            disabled={isCapturing || capturingFactionId !== null}
                                            onClick={() => handleCaptureSingleFaction(faction)}
                                        >
                                            {capturingFactionId === faction.id ? 'Capturing...' : 'Capture'}
                                        </button>
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
                {calendarAuthenticated === false && (
                    <div style={{marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.75rem'}}>
                        <span style={{fontSize: '0.85rem', color: '#888'}}>Google Calendar not connected —</span>
                        <button
                            onClick={handleConnectCalendar}
                            style={{
                                padding: '0.3rem 0.75rem',
                                fontSize: '0.85rem',
                                backgroundColor: '#1a73e8',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                            }}
                        >
                            Connect Google Calendar
                        </button>
                    </div>
                )}
                <div style={{display: 'flex', gap: '0.75rem'}}>
                    <button
                        onClick={() => handleCaptureScreen('reputations')}
                        disabled={isCapturing}
                        style={{
                            flex: 1,
                            padding: '1rem',
                            fontSize: '1.1rem',
                            backgroundColor: isCapturing ? '#ccc' : '#2196F3',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: isCapturing ? 'not-allowed' : 'pointer'
                        }}
                    >
                        Reputations
                    </button>
                    <button
                        onClick={() => handleCaptureScreen('away_team_collect')}
                        disabled={isCapturing}
                        style={{
                            flex: 1,
                            padding: '1rem',
                            fontSize: '1.1rem',
                            backgroundColor: isCapturing ? '#ccc' : '#4CAF50',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: isCapturing ? 'not-allowed' : 'pointer'
                        }}
                    >
                        Away Team<br/>Collect Only
                    </button>
                    <button
                        onClick={() => handleCaptureScreen('away_team')}
                        disabled={isCapturing}
                        style={{
                            flex: 1,
                            padding: '1rem',
                            fontSize: '1.1rem',
                            backgroundColor: isCapturing ? '#ccc' : '#388E3C',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: isCapturing ? 'not-allowed' : 'pointer'
                        }}
                    >
                        Away Team<br/>All
                    </button>
                    <button
                        onClick={() => handleCaptureScreen('gifts')}
                        disabled={isCapturing}
                        style={{
                            flex: 1,
                            padding: '1rem',
                            fontSize: '1.1rem',
                            backgroundColor: isCapturing ? '#ccc' : '#9C27B0',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: isCapturing ? 'not-allowed' : 'pointer'
                        }}
                    >
                        Gifts
                    </button>
                    <button
                        onClick={() => handleCaptureScreen('territory_capture')}
                        disabled={isCapturing}
                        style={{
                            flex: 1,
                            padding: '1rem',
                            fontSize: '1.1rem',
                            backgroundColor: isCapturing ? '#ccc' : '#00796B',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: isCapturing ? 'not-allowed' : 'pointer'
                        }}
                    >
                        Territory Capture<br/>Calendar
                    </button>
                    <button
                        onClick={() => alert('This feature is not available yet')}
                        disabled={isCapturing}
                        style={{
                            flex: 1,
                            padding: '1rem',
                            fontSize: '1.1rem',
                            backgroundColor: isCapturing ? '#ccc' : '#E65100',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: isCapturing ? 'not-allowed' : 'pointer',
                            textDecoration: 'line-through'
                        }}
                    >
                        Event Rewards
                    </button>
                </div>

                {territorySystems !== null && (
                    <div style={{marginTop: '1.5rem'}}>
                        <h3 style={{marginBottom: '0.5rem'}}>
                            Territory Capture Calendar
                            <button
                                onClick={() => setTerritorySystems(null)}
                                style={{
                                    marginLeft: '1rem',
                                    fontSize: '0.75rem',
                                    padding: '0.2rem 0.5rem',
                                    cursor: 'pointer',
                                    background: 'none',
                                    border: '1px solid #888',
                                    borderRadius: '3px',
                                    color: '#888',
                                }}
                            >
                                Clear
                            </button>
                        </h3>
                        {territorySystems.length === 0 ? (
                            <p style={{color: '#888', fontSize: '0.9rem'}}>
                                No territory systems with timers were detected. Check the debug screenshots and OCR logs.
                            </p>
                        ) : (
                            <table style={{width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem'}}>
                                <thead>
                                    <tr style={{borderBottom: '1px solid #444', textAlign: 'left'}}>
                                        <th style={{padding: '0.4rem 0.75rem'}}>System</th>
                                        <th style={{padding: '0.4rem 0.75rem'}}>Time Remaining</th>
                                        <th style={{padding: '0.4rem 0.75rem'}}>Next Takeover</th>
                                        <th style={{padding: '0.4rem 0.75rem'}}>On Calendar</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {territorySystems.map((sys, i) => {
                                        let calCell;
                                        if (sys.calendar_event === null) {
                                            calCell = <span style={{color: '#888'}} title={sys.calendar_error || 'Calendar unavailable'}>—</span>;
                                        } else if (sys.calendar_event === false) {
                                            calCell = <span style={{color: '#e57373'}} title="No event found on this date">✗ Not found</span>;
                                        } else {
                                            calCell = <span style={{color: '#81c784'}} title={`${sys.calendar_event.summary} @ ${sys.calendar_event.start}`}>✓ {sys.calendar_event.summary}</span>;
                                        }
                                        return (
                                            <tr key={i} style={{borderBottom: '1px solid #333'}}>
                                                <td style={{padding: '0.4rem 0.75rem', fontWeight: 'bold'}}>{sys.name}</td>
                                                <td style={{padding: '0.4rem 0.75rem', color: '#aaa'}}>{sys.time_remaining}</td>
                                                <td style={{padding: '0.4rem 0.75rem'}}>{sys.event_time ?? '—'}</td>
                                                <td style={{padding: '0.4rem 0.75rem'}}>{calCell}</td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        )}
                        {territorySystems.some(s => s.calendar_error) && (
                            <p style={{marginTop: '0.5rem', color: '#888', fontSize: '0.85rem'}}>
                                Google Calendar not connected — use the Connect button above, then run Territory Capture again.
                            </p>
                        )}
                    </div>
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
                </div>
                <Line ref={chartRef} options={chartOptions} data={chartData}/>
            </div>
        </div>
    );
};

export default Dashboard;
