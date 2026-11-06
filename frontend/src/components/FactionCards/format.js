/*!
 * Copyright (c) 2026 ZombieTech LLC. All rights reserved.
 *
 * SPDX-License-Identifier: PolyForm-Strict-1.0.0
 * See LICENSE in the project root for the full terms.
 *
 * Licensing inquiries: license@zombietech.biz
 */
// ai: claude-opus-5-5 | 2026-11-06
// Number and duration formatting for the faction cards, moved out of Dashboard.jsx.

/** 12_345_678 -> "12.3m" (with decimals = 1); handles k, m, b and negatives. */
export const formatShort = (value, decimals = 0) => {
    if (value == null) return null;
    const sign = value < 0 ? '-' : '';
    const abs = Math.abs(value);
    const fmt = (n) => decimals > 0 ? n.toFixed(decimals) : String(Math.floor(n));
    if (abs >= 1_000_000_000) return `${sign}${fmt(abs / 1_000_000_000)}b`;
    if (abs >= 1_000_000) return `${sign}${fmt(abs / 1_000_000)}m`;
    if (abs >= 1_000) return `${sign}${fmt(abs / 1_000)}k`;
    return `${sign}${abs}`;
};

/** 1505 -> "1d 1h 5m"; 0 or missing -> "0". */
export const formatMinutes = (minutes) => {
    const m = Math.round(minutes || 0);
    if (!m) return "0";
    const d = Math.floor(m / 1440);
    const h = Math.floor((m % 1440) / 60);
    const mins = m % 60;
    if (d > 0) return `${d}d ${h}h ${mins}m`;
    if (h > 0) return `${h}h ${mins}m`;
    return `${mins}m`;
};
