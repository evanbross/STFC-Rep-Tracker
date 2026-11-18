/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-sonnet-5 | 2026-09-14
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, errorMessage } from '../api/client';
import HostileTemplateCapture from '../components/HostileTemplateCapture';
import TargetCandidates, { useAttackTarget } from '../components/TargetCandidates';
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

const Combat = () => {
  const [running, setRunning] = useState(false);
  const [starting, setStarting] = useState(false);
  const [systemName, setSystemName] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [needsClassification, setNeedsClassification] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  // ai: claude-opus-5-5 | 2026-11-06 — true while a foreground capture runs on any page
  const captureBusy = useCaptureBusy();
  const { attackingIdx, attack } = useAttackTarget(); // ai: claude-opus-5-5 | 2026-11-06

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
      const response = await api.post('/api/capture-screen/system-targets/refresh', {
        system_name: systemNameRef.current,
        known_candidates: candidatesRef.current,
      }, { background: true });
      if (!runningRef.current) return;
      const data = response.data;
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
      handleRefreshFailure(errorMessage(e));
    }
  };

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    setMessage(null);
    clearTimeout(timerRef.current);
    try {
      const response = await api.post('/api/capture-screen/system-targets/scan');
      const data = response.data;
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
      setError(errorMessage(e));
    } finally {
      setStarting(false);
    }
  };

  const handleStop = () => {
    runningRef.current = false;
    setRunning(false);
    clearTimeout(timerRef.current);
  };

  // ai: claude-opus-5-5 | 2026-11-06 — called after TargetCandidates' confirm prompt
  const handleAttack = async (candidate, idx) => {
    // Pause the background refresh loop while we're clicking, so it can't
    // fire mid-attack and fight the mouse for control of the game window.
    clearTimeout(timerRef.current);
    setError(null);
    setMessage(null);
    const result = await attack(candidate, idx);
    if (result.launched) {
      setMessage(`Attack launched on ${candidate.name || 'target'}. Re-scanning…`);
      await handleStart(); // full re-scan — the target list just changed meaningfully
      return;
    }
    setError(result.error);
    if (runningRef.current) scheduleNextRefresh();
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
        <TargetCandidates
          candidates={candidates}
          onAttack={handleAttack}
          attackingIdx={attackingIdx}
          disabled={captureBusy}
        />
      )}
    </div>
  );
};

export default Combat;
