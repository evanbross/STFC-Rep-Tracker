/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * LICENSE: Personal Use Only
 * This source code is made available for personal, non-commercial use only.
 * You may read, study, and run this code for personal purposes.
 * You may NOT:
 *   - Use this code, in whole or in part, in any commercial product or service
 *   - Sell, sublicense, or otherwise monetize this code or derivatives of it
 *   - Redistribute this code without explicit written permission from ZombieTech LLC
 *
 * No warranty is provided, express or implied. Use at your own risk.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-sonnet-5 | 2026-09-18
import React from 'react';

// Shared between Combat.jsx and SystemTargets.jsx so the skull/diamond
// badge rendering can't silently diverge between the two candidate tables.
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
