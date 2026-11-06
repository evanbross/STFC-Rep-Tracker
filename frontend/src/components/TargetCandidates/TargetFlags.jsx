/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-sonnet-5 | 2026-09-18
import React from 'react';

// Skull/diamond badges for one candidate row; rendered only by TargetCandidates.
const TargetFlags = ({ hazard, bounty }) => {
  if (!hazard && !bounty) return null;
  return (
    <span style={{ marginLeft: '0.4rem' }}>
      {hazard && (
        <span title="Dangerous — skull glyph detected, score deprioritized" style={{ marginRight: bounty ? '0.3rem' : 0 }}>
          💀
        </span>
      )}
      {bounty && <span title="Bounty — diamond glyph detected, score boosted">💎</span>}
    </span>
  );
};

export default TargetFlags;
