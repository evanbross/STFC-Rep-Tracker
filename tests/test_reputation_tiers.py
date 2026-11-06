# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Pure tier lookups that replaced the summary's per-faction tier queries."""
import pytest

from app.database.reputation_tiers import find_next_tier, find_tier

# Shaped like ReputationsDAO.get_all(): sorted by low_limit, open top tier.
FKR_LIKE = [
    {"name": "Neutral", "low_limit": -499, "high_limit": 499},
    {"name": "Tolerated", "low_limit": 500, "high_limit": 4999},
    {"name": "Neighbor", "low_limit": 5000, "high_limit": 24999},
    {"name": "Capped", "low_limit": 25000, "high_limit": None},
]


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-499, "Neutral"), (499, "Neutral"), (500, "Tolerated"), (4999, "Tolerated"), (10**12, "Capped")],
)
def test_find_tier_bounds_are_inclusive(value: int, expected: str) -> None:
    assert find_tier(FKR_LIKE, value)["name"] == expected


def test_find_tier_below_every_tier_is_none() -> None:
    assert find_tier(FKR_LIKE, -500) is None


def test_find_tier_handles_rows_without_high_limit_key() -> None:
    """Legacy DTI-shaped rows carry messages_count/credit_amount instead of high_limit."""
    rows = [{"name": "Outsider", "low_limit": 0}, {"name": "Consort", "low_limit": 180}]

    assert find_tier(rows, 50)["name"] == "Outsider"


def test_find_next_tier_accepts_both_boundary_conventions() -> None:
    assert find_next_tier(FKR_LIKE, 4999)["name"] == "Neighbor"     # next starts at high + 1
    touching = [{"name": "A", "low_limit": 0, "high_limit": 100}, {"name": "B", "low_limit": 100, "high_limit": None}]
    assert find_next_tier(touching, 100)["name"] == "B"              # next starts at high


def test_find_next_tier_prefers_the_lower_start() -> None:
    rows = [
        {"name": "Exact", "low_limit": 100, "high_limit": 100},
        {"name": "PlusOne", "low_limit": 101, "high_limit": None},
    ]

    assert find_next_tier(rows, 100)["name"] == "Exact"


def test_find_next_tier_of_open_or_last_tier_is_none() -> None:
    assert find_next_tier(FKR_LIKE, None) is None
    assert find_next_tier(FKR_LIKE, 10**12) is None
