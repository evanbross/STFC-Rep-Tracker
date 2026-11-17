/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-17
// "Import Spock's Club" button: pick the exported .tsv, review what it holds
// for each faction, then save it as one set of readings.
import React, {useRef} from 'react';
import useSpocksClubImport from './useSpocksClubImport';

const SOURCE_LABELS = {
    filename: 'from the file name',
    file_modified: "from the file's date",
    now: 'the current time (the file has no export time)',
};

const formatChange = (value, previous) => {
    if (previous == null) return 'first reading';
    const diff = value - previous;
    return `${diff > 0 ? '+' : ''}${diff.toLocaleString()}`;
};

const overlayStyle = {
    position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
    backgroundColor: 'rgba(0,0,0,0.75)', zIndex: 1000,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
};
const panelStyle = {
    backgroundColor: '#1e1e1e', border: '1px solid #444',
    borderRadius: '8px', padding: '1.5rem', width: '560px',
    maxHeight: '80vh', overflowY: 'auto',
};

/** onSaved(): reloads the Dashboard after readings are stored. */
const SpocksClubImport = ({onSaved}) => {
    const fileInput = useRef(null);
    const {preview, timeInput, setTimeInput, busy, chooseFile, confirmImport, cancel} =
        useSpocksClubImport({onSaved});

    const onFileChosen = async (e) => {
        const [file] = e.target.files;
        e.target.value = ''; // so choosing the same file again still fires onChange
        await chooseFile(file);
    };

    return (
        <>
            <button
                className="btn-outline"
                onClick={() => fileInput.current?.click()}
                disabled={busy}
                title="Read every faction's reputation from a Spock's Club data export (.tsv)"
            >
                {busy && !preview ? 'Reading…' : "Import Spock's Club"}
            </button>
            <input
                ref={fileInput}
                type="file"
                accept=".tsv,text/tab-separated-values"
                onChange={onFileChosen}
                style={{display: 'none'}}
            />

            {preview && (
                <div style={overlayStyle}>
                    <div style={panelStyle}>
                        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem'}}>
                            <h3 style={{margin: 0}}>Import Spock's Club Export</h3>
                            <button onClick={cancel} disabled={busy} style={{
                                background: 'none', border: 'none', color: '#aaa',
                                fontSize: '1.4rem', cursor: 'pointer', lineHeight: 1,
                            }}>×</button>
                        </div>

                        {preview.readings.length === 0 ? (
                            <p>No faction in this export has a Spock's Club resource ID set. Set them on the Factions page.</p>
                        ) : (
                            <>
                                <label style={{display: 'block', fontSize: '0.85rem', color: '#aaa', marginBottom: '0.25rem'}}>
                                    Reading time ({SOURCE_LABELS[preview.exported_at_source] ?? preview.exported_at_source}):
                                </label>
                                <input
                                    type="datetime-local"
                                    step="1"
                                    value={timeInput}
                                    onChange={e => setTimeInput(e.target.value)}
                                    style={{marginBottom: '1rem'}}
                                />

                                <table>
                                    <thead>
                                    <tr>
                                        <th>Faction</th>
                                        <th className="text-right">Last saved</th>
                                        <th className="text-right">Export</th>
                                        <th className="text-right">Change</th>
                                    </tr>
                                    </thead>
                                    <tbody>
                                    {preview.readings.map(r => (
                                        <tr key={r.faction_code}>
                                            <td>{r.faction_name}</td>
                                            <td className="text-right">{r.previous_value?.toLocaleString() ?? '-'}</td>
                                            <td className="text-right">{r.value.toLocaleString()}</td>
                                            <td className="text-right">{formatChange(r.value, r.previous_value)}</td>
                                        </tr>
                                    ))}
                                    </tbody>
                                </table>
                            </>
                        )}

                        {preview.unmatched.length > 0 && (
                            <p style={{fontSize: '0.85rem', color: '#aaa', marginTop: '0.75rem'}}>
                                Not imported (no resource ID set, or not in this export): {preview.unmatched.join(', ')}
                            </p>
                        )}

                        <div style={{display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem'}}>
                            <button className="cancel" onClick={cancel} disabled={busy}>Cancel</button>
                            <button onClick={confirmImport} disabled={busy || preview.readings.length === 0}>
                                {busy ? 'Saving…' : `Save ${preview.readings.length} reading(s)`}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

export default SpocksClubImport;
