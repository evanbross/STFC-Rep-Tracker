/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// Candidate-cell formatters; Combat and SystemTargets each had a copy (N-O6).

/** "Parsteel 12,000, Tritanium 800", or an em dash when there is no cargo. */
export const formatCargo = (cargo) => {
  const entries = Object.entries(cargo || {});
  if (entries.length === 0) return '—';
  return entries.map(([resource, amount]) => `${resource} ${amount.toLocaleString()}`).join(', ');
};

/** "42.0s" under a minute, else "3m 12s"; an em dash when unknown. */
export const formatIntercept = (seconds) => {
  if (seconds == null) return '—';
  return seconds < 60 ? `${seconds.toFixed(1)}s` : `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
};
