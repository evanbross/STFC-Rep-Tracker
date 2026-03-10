import React, {useEffect, useState} from 'react';
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

    useEffect(() => {
        loadFactions();
        loadEntries();
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
        } catch (error) {
            console.error('Error loading factions:', error);
        }
    };

    const loadEntries = async () => {
        try {
            const response = await axios.get('/api/status_entries/all');
            const grouped = {};
            for (const entry of response.data) {
                if (!grouped[entry.faction_name]) grouped[entry.faction_name] = [];
                grouped[entry.faction_name].push(entry);
            }
            updateChart(grouped);
        } catch (error) {
            console.error('Error loading entries:', error);
        }
    };

    const updateChart = (data) => {
        const datasets = [];
        for (const [factionName, entries] of Object.entries(data)) {
            if (entries.length > 0) {
                const color = factionColorsMap[factionName] || 'rgb(128, 128, 128)';

                let backgroundColor = color;
                if (color.startsWith('#')) {
                    const r = parseInt(color.slice(1, 3), 16);
                    const g = parseInt(color.slice(3, 5), 16);
                    const b = parseInt(color.slice(5, 7), 16);
                    backgroundColor = `rgba(${r}, ${g}, ${b}, 0.2)`;
                } else if (color.startsWith('rgb')) {
                    backgroundColor = color.replace('rgb', 'rgba').replace(')', ', 0.2)');
                }

                datasets.push({
                    label: factionName,
                    data: entries.map(entry => ({
                        x: new Date(entry.timestamp),
                        y: entry.value
                    })),
                    borderColor: color,
                    backgroundColor: backgroundColor,
                    tension: 0.1,
                    fill: false
                });
            }
        }
        setChartData({datasets});
    };

    // Re-update chart when factionColorsMap changes
    useEffect(() => {
        if (Object.keys(factionColorsMap).length > 0) {
            loadEntries();
        }
    }, [factionColorsMap]);


    const submitEntry = async (factionName, value) => {
        try {
            await axios.post('/api/status_entries/', {
                faction: factionName,
                value: parseInt(value)
            });
            await loadFactions();
            await loadEntries();
        } catch (error) {
            console.error('Error adding entry:', error);
            alert('Failed to add entry');
        }
    };

    const handleCaptureScreen = async (screen) => {
        const urlMap = {
            reputations: '/api/capture-screen/reputations',
            away_team: '/api/capture-screen/away-team',
            gifts: '/api/capture-screen/gifts',
            event_rewards: '/api/capture-screen/event-rewards',
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
                    await loadFactions();
                    await loadEntries();
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
            } else {
                alert('Capture returned an unexpected response.');
            }
        } catch (error) {
            console.error('Error capturing screen:', error);
            alert('Failed to capture screen.');
        } finally {
            setIsCapturing(false);
        }
    };

    const handleIdentifyFaction = async () => {
        setIsCapturing(true);
        try {
            const response = await axios.post('/api/capture-screen/identify-faction');
            const data = response.data;
            if (data.faction) {
                alert(`Highlighted faction: ${data.faction}`);
            } else {
                alert(data.error || 'Could not identify faction.');
            }
        } catch (error) {
            console.error('Error identifying faction:', error);
            alert('Failed to identify faction.');
        } finally {
            setIsCapturing(false);
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
                display: true,
                position: 'top'
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
                                            <span className="status-label">Latest Value:</span>
                                            <span
                                                className="status-value">{faction.current_value?.toLocaleString()}</span>
                                        </div>
                                        <div className="status-item full-width">
                                            <span className="status-label">Value Δ:</span>
                                            <span
                                                className="status-value">{faction.last_delta >= 0 ? '+' : ''}{faction.last_delta?.toLocaleString()}</span>
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
                                            <span className="status-label">Time to {faction.status?.next_rep_level || 'Goal'}:</span>
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
                <div style={{display: 'flex', gap: '0.75rem', marginBottom: '0.75rem'}}>
                    <button
                        onClick={handleIdentifyFaction}
                        disabled={isCapturing}
                        style={{
                            padding: '0.6rem 1.2rem',
                            fontSize: '0.9rem',
                            backgroundColor: isCapturing ? '#ccc' : '#607D8B',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: isCapturing ? 'not-allowed' : 'pointer'
                        }}
                    >
                        Identify Highlighted Faction
                    </button>
                </div>
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
                        onClick={() => handleCaptureScreen('away_team')}
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
                        Away Team
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
                        onClick={() => handleCaptureScreen('event_rewards')}
                        disabled={isCapturing}
                        style={{
                            flex: 1,
                            padding: '1rem',
                            fontSize: '1.1rem',
                            backgroundColor: isCapturing ? '#ccc' : '#E65100',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: isCapturing ? 'not-allowed' : 'pointer'
                        }}
                    >
                        Event Rewards
                    </button>
                </div>
            </div>

            <div className="chart-container">
                <Line options={chartOptions} data={chartData}/>
            </div>
        </div>
    );
};

export default Dashboard;
