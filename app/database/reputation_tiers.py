# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Pure lookups over a reputation table's tier rows (N-P2).

Tier tables are small seed data, so ReputationsDAO keeps their rows in
memory and these functions answer the questions the faction summary used to
send to Postgres as three queries per faction. Rows are the dicts
ReputationsDAO.get_all() returns, sorted by low_limit; only `name`,
`low_limit` and `high_limit` are read, and `high_limit` may be absent or None.
"""
from collections.abc import Mapping, Sequence
from typing import Any

TierRow = Mapping[str, Any]


def find_tier(rows: Sequence[TierRow], value: int) -> TierRow | None:
    """Return the first tier whose range contains value (an open top counts as unbounded)."""
    for row in rows:
        high = row.get("high_limit")
        if row["low_limit"] <= value and (high is None or value <= high):
            return row
    return None


def find_next_tier(rows: Sequence[TierRow], current_high_limit: int | None) -> TierRow | None:
    """Return the tier that starts where the current one ends.

    Tables disagree on whether the next tier starts at high_limit or
    high_limit + 1, so both are accepted and the lower wins.
    """
    if current_high_limit is None:
        return None
    for row in rows:
        if row["low_limit"] in (current_high_limit, current_high_limit + 1):
            return row
    return None
