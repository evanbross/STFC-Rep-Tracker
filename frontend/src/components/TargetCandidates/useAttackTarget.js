/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// Sends one attack and tracks which row is attacking (N-O6).
import { useState } from 'react';
import { api, errorMessage } from '../../api/client';

/**
 * Returns { attackingIdx, attack }.
 *
 * attack(candidate, idx) resolves to { launched: true } or
 * { launched: false, error } and never rejects, so callers only branch on
 * the result. The confirm prompt lives in TargetCandidates, so a caller can
 * pause its own work (Combat's refresh loop) only once the user said yes.
 */
export function useAttackTarget() {
  const [attackingIdx, setAttackingIdx] = useState(null);

  const attack = async (candidate, idx) => {
    setAttackingIdx(idx);
    try {
      await api.post('/api/capture-screen/system-targets/attack', {
        click_x: candidate.click_x,
        click_y: candidate.click_y,
        vx: candidate.vx,
        vy: candidate.vy,
        scanned_at: candidate.scanned_at,
      });
      return { launched: true };
    } catch (e) {
      return { launched: false, error: errorMessage(e) };
    } finally {
      setAttackingIdx(null);
    }
  };

  return { attackingIdx, attack };
}
