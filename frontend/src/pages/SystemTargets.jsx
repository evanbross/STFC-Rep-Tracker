/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-sonnet-5 | 2026-09-14
import React, { useState } from 'react';
import { api, errorMessage } from '../api/client';
import HostileTemplateCapture from '../components/HostileTemplateCapture';
import TargetFlags from '../utils/targetFlags';
import { useCaptureBusy } from '../hooks/useCaptureBusy';

const formatCargo = (cargo) => {
  const entries = Object.entries(cargo || {});
  if (entries.length === 0) return '—';
  return entries.map(([resource, amount]) => `${resource} ${amount.toLocaleString()}`).join(', ');
};

const formatIntercept = (seconds) => {
  if (seconds == null) return '—';
  return seconds < 60 ? `${seconds.toFixed(1)}s` : `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
};

const PREFERENCE_LABELS = { target: 'Target', avoid: 'Avoid', unknown: 'Unclassified' };

const TargetTypeCard = ({ type, onSetPreference, onRename }) => {
  const [nameDraft, setNameDraft] = useState(type.display_name || '');

  return (
    <div style={{
      border: '1px solid var(--c-border, #444)', borderRadius: '8px', padding: '0.75rem',
      display: 'flex', flexDirection: 'column', gap: '0.5rem', width: '220px',
    }}>
      {type.sample_image_filename ? (
        <img
          src={`/api/target-types/sample-image/${type.sample_image_filename}`}
          alt={type.display_name || type.template_filename}
          style={{ width: '100%', height: '110px', objectFit: 'contain', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '4px' }}
        />
      ) : (
        <div style={{
          width: '100%', height: '110px', display: 'flex', alignItems: 'center', justifyContent: 'center',
          backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '4px', color: '#666', fontSize: '0.8rem',
        }}>
          No sample image
        </div>
      )}

      <input
        value={nameDraft}
        onChange={e => setNameDraft(e.target.value)}
        onBlur={() => { if (nameDraft.trim() && nameDraft !== type.display_name) onRename(type, nameDraft.trim()); }}
        style={{ width: '100%', padding: '0.3rem 0.4rem' }}
      />
      <div style={{ fontSize: '0.78rem', color: '#888' }}>
        {type.example_name ? `e.g. ${type.example_name}` : ''}
        {type.example_level != null ? ` (Lv ${type.example_level})` : ''}
        <br />
        Seen {type.times_seen}×
      </div>

      <div style={{ display: 'flex', gap: '0.4rem' }}>
        <button
          className="btn-capture"
          style={{ opacity: type.preference === 'target' ? 1 : 0.5 }}
          onClick={() => onSetPreference(type, 'target')}
        >
          Target
        </button>
        <button
          className="btn-danger"
          style={{ opacity: type.preference === 'avoid' ? 1 : 0.5 }}
          onClick={() => onSetPreference(type, 'avoid')}
        >
          Avoid
        </button>
      </div>
      <div style={{ fontSize: '0.72rem', color: '#888' }}>
        Currently: {PREFERENCE_LABELS[type.preference] || type.preference}
      </div>
    </div>
  );
};

const SystemTargets = () => {
  const [scanning, setScanning] = useState(false);
  const [attackingIdx, setAttackingIdx] = useState(null);
  const [candidates, setCandidates] = useState(null);
  const [systemName, setSystemName] = useState(null);
  const [targetTypes, setTargetTypes] = useState(null);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  // ai: claude-opus-5-5 | 2026-11-06 — disabled while any capture runs, on any page
  const captureBusy = useCaptureBusy();

  const loadTargetTypes = async (name) => {
    const response = await api.get(`/api/target-types/system/${encodeURIComponent(name)}`);
    setTargetTypes(response.data);
  };

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    setMessage(null);
    setCandidates(null);
    try {
      const response = await api.post('/api/capture-screen/system-targets/scan');
      const data = response.data;
      setSystemName(data.system_name || null);
      if (data.needs_classification) {
        setTargetTypes(data.target_types);
        setCandidates(null);
        setMessage(
          `${data.system_name}: some target types here haven't been classified yet. ` +
          `Mark each one below, then scan again.`
        );
      } else {
        setTargetTypes(null);
        setCandidates(data.candidates);
        if (data.candidates.length === 0) {
          setMessage(data.message || 'No approved targets detected on screen.');
        }
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setScanning(false);
    }
  };

  const handleSetPreference = async (type, preference) => {
    try {
      const response = await api.put(`/api/target-types/${type.id}`, { preference });
      setTargetTypes(prev => prev.map(t => t.id === type.id ? response.data : t));
    } catch (e) {
      setError(errorMessage(e, 'Failed to update target type.'));
    }
  };

  const handleRename = async (type, display_name) => {
    try {
      const response = await api.put(`/api/target-types/${type.id}`, { preference: type.preference, display_name });
      setTargetTypes(prev => prev.map(t => t.id === type.id ? response.data : t));
    } catch (e) {
      setError(errorMessage(e, 'Failed to rename target type.'));
    }
  };

  const handleAttack = async (candidate, idx) => {
    if (!window.confirm(`Attack ${candidate.name || 'this target'} (Lv ${candidate.level ?? '?'})?`)) {
      return;
    }
    setAttackingIdx(idx);
    setError(null);
    setMessage(null);
    try {
      const response = await api.post('/api/capture-screen/system-targets/attack', {
        click_x: candidate.click_x,
        click_y: candidate.click_y,
        vx: candidate.vx,
        vy: candidate.vy,
        scanned_at: candidate.scanned_at,
      });
      const data = response.data;
      if (data.error) {
        setError(data.error);
      } else {
        setMessage(`Attack launched on ${candidate.name || 'target'}.`);
      }
    } catch (e) {
      setError(e.response?.data?.error || 'Cannot reach the server. Is the backend running?');
    } finally {
      setAttackingIdx(null);
    }
  };

  const unclassifiedCount = (targetTypes || []).filter(t => t.preference === 'unknown').length;

  return (
    <div className="container">
      <h1>System Targets</h1>
      <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: '#666' }}>
        Fly your ship into a system in-game first, then scan. The first scan of a new system
        catalogs every hostile ship type present so you can mark each as a Target or something to
        Avoid — afterward, scans rank only approved types by loot, ease, and how soon your ship
        could actually reach them.
      </p>

      <HostileTemplateCapture />

      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', alignItems: 'center' }}>
        <button className="btn-capture" onClick={handleScan} disabled={scanning || captureBusy}>
          {scanning ? 'Scanning…' : 'Scan System'}
        </button>
        {systemName && <span style={{ fontSize: '0.85rem', color: '#888' }}>Current system: {systemName}</span>}
        {systemName && targetTypes === null && (
          <button className="btn-outline" onClick={() => loadTargetTypes(systemName)}>
            Review Target Types
          </button>
        )}
      </div>

      {error && <div style={{ color: 'var(--c-danger)', marginBottom: '1rem' }}>{error}</div>}
      {message && <div style={{ color: 'var(--c-success)', marginBottom: '1rem' }}>{message}</div>}

      {targetTypes && (
        <div style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <h2 style={{ margin: 0 }}>Target Types{systemName ? ` — ${systemName}` : ''}</h2>
            <button className="btn-outline" onClick={() => setTargetTypes(null)}>Close</button>
          </div>
          {unclassifiedCount > 0 && (
            <p style={{ color: 'var(--c-danger)', fontSize: '0.85rem' }}>
              {unclassifiedCount} type(s) still need to be marked Target or Avoid before scanning
              will produce attack candidates.
            </p>
          )}
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            {targetTypes.map(t => (
              <TargetTypeCard key={t.id} type={t} onSetPreference={handleSetPreference} onRename={handleRename} />
            ))}
          </div>
        </div>
      )}

      {candidates && candidates.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th className="text-right">Level</th>
              <th className="text-right">Hull</th>
              <th className="text-right">Shield</th>
              <th>Cargo</th>
              <th className="text-right">Intercept</th>
              <th className="text-right">Score</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((c, idx) => (
              <tr key={idx} style={idx === 0 ? { fontWeight: 'bold' } : {}}>
                <td>{idx === 0 ? '★ ' : ''}{c.name || 'Unknown'}<TargetFlags hazard={c.hazard} bounty={c.bounty} /></td>
                <td className="text-right">{c.level ?? '—'}</td>
                <td className="text-right">{c.hull_pct != null ? `${c.hull_pct}%` : '—'}</td>
                <td className="text-right">{c.shield_pct != null ? `${c.shield_pct}%` : '—'}</td>
                <td>{formatCargo(c.cargo)}</td>
                <td className="text-right">{formatIntercept(c.time_to_intercept_sec)}</td>
                <td className="text-right">{c.score?.toFixed(2) ?? '—'}</td>
                <td>
                  <button
                    className="btn-danger"
                    onClick={() => handleAttack(c, idx)}
                    disabled={attackingIdx !== null || captureBusy}
                  >
                    {attackingIdx === idx ? 'Attacking…' : 'Attack'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default SystemTargets;
