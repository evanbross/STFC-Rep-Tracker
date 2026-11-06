/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// The ranked attack-candidate table shared by Combat and System Targets (N-O6).
import React from 'react';
import TargetFlags from './TargetFlags';
import { formatCargo, formatIntercept } from './format';

/**
 * candidates: ranked best-first; the first row is starred.
 * onAttack(candidate, idx): called only after the user confirms.
 * attackingIdx: row whose attack is in flight (null when none).
 * disabled: true while any capture runs, so no second automation starts.
 */
const TargetCandidates = ({ candidates, onAttack, attackingIdx, disabled }) => {
  const handleAttackClick = (candidate, idx) => {
    if (window.confirm(`Attack ${candidate.name || 'this target'} (Lv ${candidate.level ?? '?'})?`)) {
      onAttack(candidate, idx);
    }
  };

  return (
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
                onClick={() => handleAttackClick(c, idx)}
                disabled={attackingIdx !== null || disabled}
              >
                {attackingIdx === idx ? 'Attacking…' : 'Attack'}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};

export default TargetCandidates;
