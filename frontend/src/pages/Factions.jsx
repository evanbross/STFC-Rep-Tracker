/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
import React, {useEffect, useState} from 'react';
import { api, errorMessage } from '../api/client';

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

const SNIPPET_TYPES = ['button', 'desc'];

const SnippetsModal = ({ faction, onClose }) => {
    const [snippets, setSnippets] = useState([]);
    const [pendingFile, setPendingFile] = useState(null);   // { file: File, previewUrl: string }
    const [newFilename, setNewFilename] = useState('');
    const [newType, setNewType] = useState('desc');
    const [uploading, setUploading] = useState(false);
    const [pasteActive, setPasteActive] = useState(false);
    const fileInputRef = React.useRef();
    const pasteZoneRef = React.useRef();

    const nextSnippetFilename = (type, ext = 'png') => {
        const factionCode = (faction.code || faction.name).toUpperCase();
        const prefix = `Selected-${type}-${factionCode}-`;
        const usedNumbers = snippets
            .map(s => { const m = s.filename.match(new RegExp(`^${prefix}(\\d+)\\.`, 'i')); return m ? parseInt(m[1]) : 0; })
            .filter(Boolean);
        const next = usedNumbers.length > 0 ? Math.max(...usedNumbers) + 1 : 1;
        return `${prefix}${next}.${ext}`;
    };

    const loadSnippets = () => {
        api.get(`/api/factions/${faction.id}/selected-snippets`)
            .then(r => setSnippets(r.data))
            .catch(err => console.error('Error loading snippets:', err));
    };

    useEffect(() => { loadSnippets(); }, [faction.id]);

    // Revoke the pending preview's object URL on unmount (e.g. modal close)
    const pendingFileRef = React.useRef(pendingFile);
    pendingFileRef.current = pendingFile;
    useEffect(() => {
        return () => {
            if (pendingFileRef.current) URL.revokeObjectURL(pendingFileRef.current.previewUrl);
        };
    }, []);

    // Global paste listener when paste zone is active
    useEffect(() => {
        if (!pasteActive) return;
        const handlePaste = (e) => {
            const item = Array.from(e.clipboardData.items).find(i => i.type.startsWith('image/'));
            if (!item) return;
            const file = item.getAsFile();
            setPendingFile(prev => {
                if (prev) URL.revokeObjectURL(prev.previewUrl);
                return { file, previewUrl: URL.createObjectURL(file) };
            });
            setNewFilename(nextSnippetFilename(newType));
        };
        window.addEventListener('paste', handlePaste);
        return () => window.removeEventListener('paste', handlePaste);
    }, [pasteActive, newType, snippets, faction.code, faction.name]);

    const handleFileSelect = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setPendingFile(prev => {
            if (prev) URL.revokeObjectURL(prev.previewUrl);
            return { file, previewUrl: URL.createObjectURL(file) };
        });
        if (!newFilename) setNewFilename(file.name);
    };

    const handleClipboardPaste = async () => {
        try {
            const items = await navigator.clipboard.read();
            const imageItem = items.find(item => item.types.some(t => t.startsWith('image/')));
            if (!imageItem) { alert('No image found in clipboard.'); return; }
            const type = imageItem.types.find(t => t.startsWith('image/'));
            const blob = await imageItem.getType(type);
            const ext = type.split('/')[1] || 'png';
            const file = new File([blob], 'pasted', { type });
            clearPending();
            setPendingFile({ file, previewUrl: URL.createObjectURL(blob) });
            setNewFilename(nextSnippetFilename(newType, ext));
        } catch (err) {
            alert('Could not read clipboard. Make sure an image is copied and clipboard access is allowed.');
        }
    };

    const clearPending = () => {
        if (pendingFile) URL.revokeObjectURL(pendingFile.previewUrl);
        setPendingFile(null);
        setNewFilename('');
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const handleUpload = async () => {
        if (!pendingFile || !newFilename.trim()) return;
        setUploading(true);
        try {
            const fd = new FormData();
            fd.append('file', pendingFile.file);
            fd.append('filename', newFilename.trim());
            fd.append('snippet_type', newType);
            await api.post(`/api/factions/${faction.id}/selected-snippets`, fd);
            clearPending();
            setPasteActive(false);
            loadSnippets();
        } catch (err) {
            console.error('Upload failed:', err);
            alert(`Upload failed: ${errorMessage(err)}`); // ai: claude-opus-5-5 | 2026-11-06
        } finally {
            setUploading(false);
        }
    };

    // ai: claude-opus-5-5 | 2026-11-18
    // The server deletes an uploaded image with its record unless something else still uses it.
    const handleDelete = async (snippet) => {
        const fileNote = snippet.uploaded
            ? 'The uploaded image is deleted too, unless another snippet or faction still uses it.'
            : 'The image file is kept.';
        if (!window.confirm(`Delete this snippet record? ${fileNote}`)) return;
        try {
            await api.delete(`/api/factions/selected-snippets/${snippet.id}`);
            loadSnippets();
        } catch (err) {
            console.error('Delete failed:', err);
            alert(`Delete failed: ${errorMessage(err)}`); // ai: claude-opus-5-5 | 2026-11-06
        }
    };

    const byType = snippets.reduce((acc, s) => {
        const key = s.snippet_type || 'other';
        (acc[key] = acc[key] || []).push(s);
        return acc;
    }, {});

    const cardStyle = {
        border: '1px solid #333', borderRadius: 6, padding: 8,
        background: '#2a2a3e', textAlign: 'center', width: 170, flexShrink: 0,
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
    };

    return (
        <div style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }} onClick={onClose}>
            <div style={{
                background: '#1e1e2e', border: '1px solid #444', borderRadius: 8,
                padding: 24, maxWidth: 760, width: '92%', maxHeight: '85vh',
                overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16,
            }} onClick={e => e.stopPropagation()}>

                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h2 style={{ margin: 0, color: '#e8e8f0' }}>{faction.name} — Selected Snippets</h2>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#aaa', fontSize: 20, cursor: 'pointer' }}>✕</button>
                </div>

                {/* Existing snippets */}
                {snippets.length === 0 && <p style={{ color: '#888', margin: 0 }}>No selected snippets configured.</p>}
                {Object.entries(byType).map(([type, items]) => (
                    <div key={type}>
                        <div style={{ fontSize: 11, textTransform: 'uppercase', color: '#888', letterSpacing: 1, marginBottom: 8 }}>{type}</div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                            {items.map(s => (
                                <div key={s.id} style={cardStyle}>
                                    <img
                                        src={`/api/factions/snippet-image/${encodeURIComponent(s.filename)}`}
                                        alt={s.filename}
                                        style={{ maxWidth: 150, maxHeight: 75, objectFit: 'contain' }}
                                        onError={e => { e.target.style.display = 'none'; }}
                                    />
                                    <div style={{ fontSize: 10, color: '#888', wordBreak: 'break-all', lineHeight: 1.3 }}>{s.filename}</div>
                                    <button
                                        onClick={() => handleDelete(s)}
                                        style={{ fontSize: 11, padding: '2px 10px', background: '#5a1a1a', border: '1px solid #8b2020', borderRadius: 4, color: '#f88', cursor: 'pointer' }}
                                    >Delete</button>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}

                {/* Add snippet section */}
                <div style={{ borderTop: '1px solid #333', paddingTop: 16 }}>
                    <div style={{ fontSize: 12, color: '#aaa', marginBottom: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>Add Snippet</div>

                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 10 }}>
                        <select
                            value={newType}
                            onChange={e => setNewType(e.target.value)}
                            style={{ padding: '4px 8px', background: '#2a2a3e', border: '1px solid #444', borderRadius: 4, color: '#eee' }}
                        >
                            {SNIPPET_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                            <option value="">other</option>
                        </select>

                        <input
                            type="text"
                            placeholder="Filename (e.g. Selected-Button-Fed.jpg)"
                            value={newFilename}
                            onChange={e => setNewFilename(e.target.value)}
                            style={{ flex: 1, minWidth: 220, padding: '4px 8px', background: '#2a2a3e', border: '1px solid #444', borderRadius: 4, color: '#eee' }}
                        />
                    </div>

                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                        {/* File picker */}
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*"
                            style={{ display: 'none' }}
                            onChange={handleFileSelect}
                        />
                        <button
                            onClick={() => fileInputRef.current.click()}
                            style={{ padding: '5px 14px', background: '#2a2a3e', border: '1px solid #555', borderRadius: 4, color: '#ccc', cursor: 'pointer' }}
                        >Browse…</button>

                        <button
                            onClick={handleClipboardPaste}
                            style={{ padding: '5px 14px', background: '#2a2a3e', border: '1px solid #555', borderRadius: 4, color: '#ccc', cursor: 'pointer' }}
                        >Paste from Clipboard</button>

                        {/* Paste toggle */}
                        <button
                            onClick={() => { setPasteActive(p => !p); clearPending(); }}
                            style={{
                                padding: '5px 14px', borderRadius: 4, cursor: 'pointer',
                                background: pasteActive ? '#1a3a5a' : '#2a2a3e',
                                border: `1px solid ${pasteActive ? '#3a7abf' : '#555'}`,
                                color: pasteActive ? '#7ac' : '#ccc',
                            }}
                        >{pasteActive ? 'Cancel Paste' : 'Paste Image'}</button>

                        {pendingFile && (
                            <button
                                onClick={handleUpload}
                                disabled={uploading || !newFilename.trim()}
                                style={{ padding: '5px 14px', background: '#1a4a1a', border: '1px solid #2a8a2a', borderRadius: 4, color: '#8f8', cursor: 'pointer' }}
                            >{uploading ? 'Saving…' : 'Save'}</button>
                        )}
                        {pendingFile && (
                            <button onClick={clearPending} style={{ padding: '5px 14px', background: '#2a2a3e', border: '1px solid #555', borderRadius: 4, color: '#aaa', cursor: 'pointer' }}>Clear</button>
                        )}
                    </div>

                    {/* Paste zone hint */}
                    {pasteActive && !pendingFile && (
                        <div
                            ref={pasteZoneRef}
                            style={{
                                marginTop: 10, border: '2px dashed #3a7abf', borderRadius: 6,
                                padding: '20px', textAlign: 'center', color: '#7ac', fontSize: 13,
                                background: '#1a2a3a',
                            }}
                        >
                            Press Ctrl+V to paste an image from your clipboard
                        </div>
                    )}

                    {/* Preview */}
                    {pendingFile && (
                        <div style={{ marginTop: 10, display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                            <img
                                src={pendingFile.previewUrl}
                                alt="preview"
                                style={{ maxWidth: 200, maxHeight: 100, objectFit: 'contain', border: '1px solid #444', borderRadius: 4 }}
                            />
                            <div style={{ fontSize: 11, color: '#888' }}>
                                <div>{pendingFile.file.name}</div>
                                <div>{(pendingFile.file.size / 1024).toFixed(1)} KB</div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

// ai: claude-sonnet-5 | 2026-07-10
const EMPTY_FORM_DATA = {
    id: null, name: '', code: '', color: '',
    reputation_table_name: '', on_chart: 0, display_order: '',
    reputation_dao_name: '', snippet_selected_button: '', snippet_unselected: '',
    spocks_resource_id: '' // ai: claude-opus-5-5 | 2026-11-17
};

const Factions = () => {
    const [factions, setFactions] = useState([]);
    const [showForm, setShowForm] = useState(false);
    const [snippetFaction, setSnippetFaction] = useState(null);
    const [formData, setFormData] = useState(EMPTY_FORM_DATA);
    const [reputationTypes, setReputationTypes] = useState([]); // ai: claude-opus-5-5 | 2026-11-06

    useEffect(() => {
        loadFactions();
        // ai: claude-opus-5-5 | 2026-11-06
        api.get('/api/reputations/types')
            .then(r => setReputationTypes(r.data))
            .catch(error => console.error('Error loading reputation types:', error));
    }, []);

    const loadFactions = async () => {
        try {
            const response = await api.get('/api/factions');
            setFactions(response.data);
        } catch (error) {
            console.error('Error loading factions:', error);
        }
    };

    const handleEdit = (faction) => {
        // ai: claude-sonnet-5 | 2026-07-10
        setFormData({
            id: faction.id,
            name: faction.name,
            code: faction.code || '',
            color: faction.color || '',
            reputation_table_name: faction.reputation_table_name || '',
            on_chart: faction.on_chart || 0,
            display_order: faction.display_order ?? '',
            reputation_dao_name: faction.reputation_dao_name || '',
            snippet_selected_button: faction.snippet_selected_button || '',
            snippet_unselected: faction.snippet_unselected || '',
            spocks_resource_id: faction.spocks_resource_id ?? '' // ai: claude-opus-5-5 | 2026-11-17
        });
        setShowForm(true);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            if (formData.id) {
                await api.put(`/api/factions/${formData.id}`, formData);
            } else {
                await api.post('/api/factions', formData);
            }
            setShowForm(false);
            setFormData(EMPTY_FORM_DATA);
            loadFactions();
        } catch (error) {
            console.error('Error saving faction:', error);
            alert(`Failed to save faction: ${errorMessage(error)}`); // ai: claude-opus-5-5 | 2026-11-06
        }
    };

    return (
        <div className="factions-page">
        {snippetFaction && <SnippetsModal faction={snippetFaction} onClose={() => setSnippetFaction(null)} />}
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
                        {/* ai: claude-opus-5-5 | 2026-11-06 — one choice per *_reputations_dao.py (R5); the DAO name follows */}
                        <div className="form-group">
                            <label>Reputation Type:</label>
                            <select
                                value={formData.reputation_table_name}
                                onChange={e => {
                                    const chosen = reputationTypes.find(t => t.table_name === e.target.value);
                                    setFormData({
                                        ...formData,
                                        reputation_table_name: chosen?.table_name ?? '',
                                        reputation_dao_name: chosen?.dao_name ?? '',
                                    });
                                }}
                            >
                                <option value="">(none)</option>
                                {reputationTypes.map(t => (
                                    <option key={t.table_name} value={t.table_name}>{t.table_name}</option>
                                ))}
                            </select>
                        </div>
                        <div className="form-row">
                            <div className="form-group">
                                <label>Selected Button Snippet:</label>
                                <input
                                    type="text"
                                    value={formData.snippet_selected_button}
                                    onChange={e => setFormData({...formData, snippet_selected_button: e.target.value})}
                                    placeholder="e.g. Selected-Button-Fed.jpg"
                                />
                            </div>
                            <div className="form-group">
                                <label>Unselected Button Snippet:</label>
                                <input
                                    type="text"
                                    value={formData.snippet_unselected}
                                    onChange={e => setFormData({...formData, snippet_unselected: e.target.value})}
                                    placeholder="e.g. Unselected-Button-Fed.jpg"
                                />
                            </div>
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
                                {/* ai: claude-opus-5-5 | 2026-11-07 — every faction is in the chart legend; this picks its starting visibility (N-B4) */}
                                <label>On Chart:</label>
                                <select
                                    value={formData.on_chart}
                                    onChange={e => setFormData({...formData, on_chart: parseInt(e.target.value)})}
                                    title="Whether the Dashboard chart shows this faction when it loads. Click its legend entry to show or hide it anytime."
                                >
                                    <option value={0}>Hidden at load</option>
                                    <option value={1}>Shown at load</option>
                                </select>
                            </div>
                        </div>
                        {/* ai: claude-opus-5-5 | 2026-11-17 — matched by ID: names repeat in the export */}
                        <div className="form-group">
                            <label>Spock's Club Resource ID:</label>
                            <input
                                type="text"
                                inputMode="numeric"
                                pattern="[0-9]*"
                                value={formData.spocks_resource_id}
                                onChange={e => setFormData({...formData, spocks_resource_id: e.target.value.trim()})}
                                placeholder="e.g. 970475396 (Federation Points); blank to skip in imports"
                                title="The EntityId of this faction's reputation resource in a Spock's Club export"
                            />
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
                            <td className="text-right">{f.on_chart ? 'Shown' : 'Hidden'}</td>{/* ai: claude-opus-5-5 | 2026-11-07 */}
                            <td>
                                <button className="action-btn edit-btn" onClick={() => handleEdit(f)}>Edit</button>
                                <button className="action-btn" onClick={() => setSnippetFaction(f)} style={{ marginLeft: 6 }}>Snippets</button>
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
