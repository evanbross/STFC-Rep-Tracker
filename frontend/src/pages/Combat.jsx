/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-sonnet-5 | 2026-09-14
import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import HostileTemplateCapture from '../components/HostileTemplateCapture';
import TargetFlags from '../utils/targetFlags';
import { isCaptureBusyError, useCaptureBusy } from '../hooks/useCaptureBusy';

// How often to poll refresh_targets() while combat mode is running. This is
// a frontend pacing knob, not a screen-scraping parameter, so it lives here
// rather than in settings.yaml.
const REFRESH_INTERVAL_MS = 4000;
// A transient failure (a dialog briefly covering the window, a dropped
// capture) shouldn't halt combat mode — retry on the same interval instead.
// Only give up after this many *consecutive* failures, so a genuinely dead
// backend/window doesn't retry forever.
const MAX_CONSECUTIVE_REFRESH_ERRORS = 10;

const formatCargo = (cargo) => {
  const entries = Object.entries(cargo || {});
  if (entries.length === 0) return '—';
  return entries.map(([resource, amount]) => `${resource} ${amount.toLocaleString()}`).join(', ');
};

const formatIntercept = (seconds) => {
  if (seconds == null) return '—';
  return seconds < 60 ? `${seconds.toFixed(1)}s` : `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
};

const Combat = () => {
  const [running, setRunning] = useState(false);
  const [starting, setStarting] = useState(false);
  const [systemName, setSystemName] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [needsClassification, setNeedsClassification] = useState(false);
  const [attackingIdx, setAttackingIdx] = useState(null);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  // ai: claude-opus-5-5 | 2026-11-06 — true while a foreground capture runs on any page
  const captureBusy = useCaptureBusy();

  // Refs mirror state that async continuations (the refresh loop, the
  // in-flight attack) need to read without capturing a stale closure.
  const runningRef = useRef(false);
  const candidatesRef = useRef([]);
  const systemNameRef = useRef(null);
  const timerRef = useRef(null);
  const consecutiveErrorsRef = useRef(0);

  useEffect(() => {
    // Stop the loop and clear any pending timer when navigating away.
    return () => {
      runningRef.current = false;
      clearTimeout(timerRef.current);
    };
  }, []);

  const scheduleNextRefresh = () => {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(doRefresh, REFRESH_INTERVAL_MS);
  };

  // A failed refresh retries on the same interval rather than stopping —
  // transient capture hiccups shouldn't end combat mode. Only gives up after
  // MAX_CONSECUTIVE_REFRESH_ERRORS in a row, since an error that never
  // clears (window closed, backend down) shouldn't retry forever.
  const handleRefreshFailure = (errorText) => {
    if (!runningRef.current) return;
    consecutiveErrorsRef.current += 1;
    const count = consecutiveErrorsRef.current;
    if (count >= MAX_CONSECUTIVE_REFRESH_ERRORS) {
      setError(`${errorText} (stopped after ${count} consecutive failures)`);
      runningRef.current = false;
      setRunning(false);
      return;
    }
    setError(`${errorText} (retrying — ${count} consecutive failure${count > 1 ? 's' : ''})`);
    scheduleNextRefresh();
  };

  const doRefresh = async () => {
    if (!runningRef.current) return;
    try {
      // ai: claude-opus-5-5 | 2026-11-06 — background: polling must not flicker the capture buttons
      const response = await axios.post('/api/capture-screen/system-targets/refresh', {
        system_name: systemNameRef.current,
        known_candidates: candidatesRef.current,
      }, { background: true });
      if (!runningRef.current) return;
      const data = response.data;
      if (data.error) {
        handleRefreshFailure(data.error);
        return;
      }
      consecutiveErrorsRef.current = 0;
      setError(null);
      setCandidates(data.candidates);
      candidatesRef.current = data.candidates;
      scheduleNextRefresh();
    } catch (e) {
      if (!runningRef.current) return;
      // ai: claude-opus-5-5 | 2026-11-06
      // Another capture (an attack, or one started on another page) holds the
      // game; skip this tick quietly instead of counting it as a failure.
      if (isCaptureBusyError(e)) {
        scheduleNextRefresh();
        return;
      }
      handleRefreshFailure(e.response?.data?.error || 'Cannot reach the server. Is the backend running?');
    }
  };

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    setMessage(null);
    clearTimeout(timerRef.current);
    try {
      const response = await axios.post('/api/capture-screen/system-targets/scan');
      const data = response.data;
      if (data.error) {
        setError(data.error);
        return;
      }
      setSystemName(data.system_name || null);
      systemNameRef.current = data.system_name || null;

      if (data.needs_classification) {
        setNeedsClassification(true);
        setCandidates([]);
        candidatesRef.current = [];
        return;
      }

      setNeedsClassification(false);
      setCandidates(data.candidates);
      candidatesRef.current = data.candidates;
      if (data.candidates.length === 0) {
        setMessage(data.message || 'No approved targets detected on screen.');
      }

      consecutiveErrorsRef.current = 0;
      runningRef.current = true;
      setRunning(true);
      scheduleNextRefresh();
    } catch (e) {
      setError(e.response?.data?.error || 'Cannot reach the server. Is the backend running?');
    } finally {
      setStarting(false);
    }
  };

  const handleStop = () => {
    runningRef.current = false;
    setRunning(false);
    clearTimeout(timerRef.current);
  };

  const handleAttack = async (candidate, idx) => {
    if (!window.confirm(`Attack ${candidate.name || 'this target'} (Lv ${candidate.level ?? '?'})?`)) {
      return;
    }
    // Pause the background refresh loop while we're clicking, so it can't
    // fire mid-attack and fight the mouse for control of the game window.
    clearTimeout(timerRef.current);
    setAttackingIdx(idx);
    setError(null);
    setMessage(null);
    try {
      const response = await axios.post('/api/capture-screen/system-targets/attack', {
        click_x: candidate.click_x,
        click_y: candidate.click_y,
        vx: candidate.vx,
        vy: candidate.vy,
        scanned_at: candidate.scanned_at,
      });
      const data = response.data;
      if (data.error) {
        setError(data.error);
        if (runningRef.current) scheduleNextRefresh();
      } else {
        setMessage(`Attack launched on ${candidate.name || 'target'}. Re-scanning…`);
        setAttackingIdx(null);
        await handleStart(); // full re-scan — the target list just changed meaningfully
        return;
      }
    } catch (e) {
      setError(e.response?.data?.error || 'Cannot reach the server. Is the backend running?');
      if (runningRef.current) scheduleNextRefresh();
    } finally {
      setAttackingIdx(null);
    }
  };

  return (
    <div className="container">
      <h1>Combat</h1>
      <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: '#666' }}>
        Start combat mode once you're looking at a system with your ship stationary. The target
        list re-ranks itself every few seconds from fresh position data (no clicking involved) —
        cargo/hull/shield are only re-measured on a full re-scan, which happens automatically
        after you attack.
      </p>

      <HostileTemplateCapture />

      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', alignItems: 'center' }}>
        {!running ? (
          <button className="btn-capture" onClick={handleStart} disabled={starting || captureBusy}>
            {starting ? 'Starting…' : 'Start Combat'}
          </button>
        ) : (
          <button className="btn-outline" onClick={handleStop}>Stop</button>
        )}
        {systemName && <span style={{ fontSize: '0.85rem', color: '#888' }}>System: {systemName}</span>}
        {running && <span style={{ fontSize: '0.8rem', color: 'var(--c-success)' }}>● live</span>}
      </div>

      {error && <div style={{ color: 'var(--c-danger)', marginBottom: '1rem' }}>{error}</div>}
      {message && <div style={{ color: 'var(--c-success)', marginBottom: '1rem' }}>{message}</div>}

      {needsClassification && (
        <div style={{ color: 'var(--c-danger)', marginBottom: '1rem' }}>
          {systemName} has unclassified target types. Go to{' '}
          <Link to="/system-targets">System Targets</Link> to mark each one Target or Avoid,
          then come back and start combat again.
        </div>
      )}

      {candidates.length > 0 && (
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

export default Combat;
