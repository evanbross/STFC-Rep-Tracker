import React, {useEffect, useState} from 'react';
import axios from 'axios';

const getContrastingColor = (hexcolor) => {
    if (!hexcolor) return '#555';

    // Handle named colors
    const temp = document.createElement('div');
    temp.style.color = hexcolor;
    document.body.appendChild(temp);
    const rgb = window.getComputedStyle(temp).color;
    document.body.removeChild(temp);

    const match = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (!match) return '#555';

    const r = parseInt(match[1]);
    const g = parseInt(match[2]);
    const b = parseInt(match[3]);

    // Calculate luminance
    const yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000;
    return (yiq >= 128) ? 'black' : 'white';
};

const Factions = () => {
    const [factions, setFactions] = useState([]);
    const [showForm, setShowForm] = useState(false);
    const [formData, setFormData] = useState({
        id: null,
        name: '',
        code: '',
        color: '',
        reputation_table_name: '',
        on_chart: 0,
        display_order: ''
    });

    useEffect(() => {
        loadFactions();
    }, []);

    const loadFactions = async () => {
        try {
            const response = await axios.get('/api/factions');
            setFactions(response.data);
        } catch (error) {
            console.error('Error loading factions:', error);
        }
    };

    const handleEdit = (faction) => {
        setFormData({
            id: faction.id,
            name: faction.name,
            code: faction.code || '',
            color: faction.color || '',
            reputation_table_name: faction.reputation_table_name || '',
            on_chart: faction.on_chart || 0,
            display_order: faction.display_order ?? ''
        });
        setShowForm(true);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            if (formData.id) {
                await axios.put(`/api/factions/${formData.id}`, formData);
            } else {
                await axios.post('/api/factions', formData);
            }
            setShowForm(false);
            setFormData({
                id: null,
                name: '',
                code: '',
                color: '',
                reputation_table_name: '',
                on_chart: 0,
                display_order: ''
            });
            loadFactions();
        } catch (error) {
            console.error('Error saving faction:', error);
            alert('Failed to save faction');
        }
    };

    return (
        <div className="factions-page">
            <h1>Factions Management</h1>

            {!showForm ? (
                <button onClick={() => setShowForm(true)} style={{marginBottom: '20px'}}>Add New Faction</button>
            ) : (
                <div className="container">
                    <h2>{formData.id ? 'Edit Faction' : 'Add New Faction'}</h2>
                    <form onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label>Faction Name:</label>
                            <input
                                type="text"
                                value={formData.name}
                                onChange={e => setFormData({...formData, name: e.target.value})}
                                required
                            />
                        </div>
                        <div className="form-row">
                            <div className="form-group">
                                <label>Code:</label>
                                <input
                                    type="text"
                                    value={formData.code}
                                    onChange={e => setFormData({...formData, code: e.target.value})}
                                    placeholder="e.g. FED"
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label>Color:</label>
                                <input
                                    type="text"
                                    value={formData.color}
                                    onChange={e => setFormData({...formData, color: e.target.value})}
                                    placeholder="e.g. royalblue"
                                />
                            </div>
                        </div>
                        <div className="form-group">
                            <label>Reputation Table Name:</label>
                            <input
                                type="text"
                                value={formData.reputation_table_name}
                                onChange={e => setFormData({...formData, reputation_table_name: e.target.value})}
                                placeholder="e.g. fkr_reputations"
                            />
                        </div>
                        <div className="form-row">
                            <div className="form-group">
                                <label>Display Order:</label>
                                <input
                                    type="number"
                                    value={formData.display_order}
                                    onChange={e => setFormData({...formData, display_order: e.target.value})}
                                />
                            </div>
                            <div className="form-group">
                                <label>On Chart:</label>
                                <select
                                    value={formData.on_chart}
                                    onChange={e => setFormData({...formData, on_chart: parseInt(e.target.value)})}
                                >
                                    <option value={0}>No</option>
                                    <option value={1}>Yes</option>
                                </select>
                            </div>
                        </div>
                        <button type="submit">Save Faction</button>
                        <button type="button" className="cancel" onClick={() => setShowForm(false)}>Cancel</button>
                    </form>
                </div>
            )}

            <div className="container">
                <table>
                    <thead>
                    <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Rep Table</th>
                        <th className="text-right">Order</th>
                        <th className="text-right">On Chart</th>
                        <th>Actions</th>
                    </tr>
                    </thead>
                    <tbody>
                    {factions.map(f => (
                        <tr key={f.id}>
                            <td>{f.name}</td>
                            <td>
                  <span
                      className="code-badge"
                      style={{
                          backgroundColor: f.color || '#e0e0e0',
                          color: getContrastingColor(f.color),
                          borderColor: 'rgba(0,0,0,0.1)'
                      }}
                  >
                    {f.faction_type}
                  </span>
                            </td>
                            <td>{f.reputation_table_name || '-'}</td>
                            <td className="text-right">{f.display_order ?? '-'}</td>
                            <td className="text-right">{f.on_chart ?? 0}</td>
                            <td>
                                <button className="action-btn edit-btn" onClick={() => handleEdit(f)}>Edit</button>
                            </td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default Factions;
