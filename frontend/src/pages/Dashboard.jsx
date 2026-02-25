import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, TimeScale } from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale
);

const Dashboard = () => {
  const [factions, setFactions] = useState([]);
  const [selectedFaction, setSelectedFaction] = useState(null);
  const [newValue, setNewValue] = useState('');
  const [chartData, setChartData] = useState({ datasets: [] });
  const [factionColorsMap, setFactionColorsMap] = useState({});

  useEffect(() => {
    loadFactions();
    loadEntries();
  }, []);

  const loadFactions = async () => {
    try {
      const response = await axios.get('/api/factions/summary');
      let factionList = response.data;

      const CODE_ORDER = ['AUG', 'FED', 'KLI', 'ROM', 'ROG', 'BAJ', 'TER', 'DTI', 'S31', 'EXB'];
      const codeIndex = (code) => {
        const idx = CODE_ORDER.indexOf(code || '');
        return idx === -1 ? Number.MAX_SAFE_INTEGER : idx;
      };

      factionList.sort((a, b) => {
        const aHas = typeof a.display_order === 'number';
        const bHas = typeof b.display_order === 'number';
        if (aHas && bHas && a.display_order !== b.display_order) return a.display_order - b.display_order;
        if (aHas && !bHas) return -1;
        if (!aHas && bHas) return 1;
        const ci = codeIndex(a.faction_type) - codeIndex(b.faction_type);
        if (ci !== 0) return ci;
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
      const response = await axios.get('/api/entries');
      updateChart(response.data);
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
    setChartData({ datasets });
  };

  // Re-update chart when factionColorsMap changes
  useEffect(() => {
    if (Object.keys(factionColorsMap).length > 0) {
      loadEntries();
    }
  }, [factionColorsMap]);

  const handleAddEntry = async (e) => {
    e.preventDefault();
    if (!selectedFaction || !newValue) {
      alert('Please select a faction and enter a value');
      return;
    }
    await submitEntry(selectedFaction.name, newValue);
    setNewValue('');
  };

  const submitEntry = async (factionName, value) => {
    try {
      await axios.post('/api/entries', {
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
      }
    }
  };

  return (
    <div className="dashboard">
      <h1>STFC Reputation Tracker</h1>

      <div className="container">
        <h2>Add New Entry</h2>
        <form onSubmit={handleAddEntry}>
          <div className="form-group">
            <label>Select Faction:</label>
            <div className="faction-buttons">
              {factions.map(faction => {
                const isSelected = selectedFaction?.name === faction.name;
                let factionNameStyle = faction.color ? { color: faction.color } : {};
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
                        <span className="status-value">{faction.current_value?.toLocaleString()}</span>
                      </div>
                      <div className="status-item full-width">
                        <span className="status-label">Value Δ:</span>
                        <span className="status-value">{faction.last_delta >= 0 ? '+' : ''}{faction.last_delta?.toLocaleString()}</span>
                      </div>
                      <div className="status-item">
                        <span className="status-label">Change Rate:</span>
                        <span className="status-value">{faction.status?.raw_change_per_minute || 0}/min</span>
                      </div>
                      <div className="status-item">
                        <span className="status-label">Time:</span>
                        <span className="status-value">{faction.status?.minutes || 0}m</span>
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
                          const input = e.target.previousSibling;
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
          <div className="form-group">
            <label htmlFor="value">Reputation Value (Selected: {selectedFaction?.name || 'None'}):</label>
            <input 
              type="number" 
              id="value" 
              value={newValue}
              onChange={e => setNewValue(e.target.value)}
              placeholder="Enter reputation value"
            />
          </div>
          <button type="submit" style={{ width: '100%' }}>Add Entry</button>
        </form>
      </div>

      <div className="chart-container">
        <Line options={chartOptions} data={chartData} />
      </div>
    </div>
  );
};

export default Dashboard;
