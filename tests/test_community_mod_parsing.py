# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-19
"""Reading resource amounts out of community-mod payloads (pure, no app or DB)."""
from typing import Any

import pytest

from app.community_mod_parsing import resource_amounts

FED_ID = 970475396


def test_reads_resource_records_and_ignores_other_types() -> None:
    payload = [
        {"type": "resource", "rid": FED_ID, "amount": 1045097591},
        {"type": "alliance_resource", "rid": 3632155109, "amount": 205145286},
        {"type": "officer", "oid": 4066988596, "level": 30},
        {"type": "resource", "rid": 908921776, "amount": 828291},
    ]

    assert resource_amounts(payload) == {FED_ID: 1045097591, 908921776: 828291}


def test_a_later_record_for_the_same_rid_wins() -> None:
    payload = [
        {"type": "resource", "rid": FED_ID, "amount": 1},
        {"type": "resource", "rid": FED_ID, "amount": 2},
    ]

    assert resource_amounts(payload) == {FED_ID: 2}


@pytest.mark.parametrize("record", [
    {"type": "resource", "rid": FED_ID},
    {"type": "resource", "amount": 5},
    {"type": "resource", "rid": str(FED_ID), "amount": 5},
    {"type": "resource", "rid": FED_ID, "amount": 5.5},
    {"type": "resource", "rid": FED_ID, "amount": True},
    {"type": "resource", "rid": None, "amount": 5},
    "resource",
    None,
])
def test_malformed_records_are_skipped(record: Any) -> None:
    assert resource_amounts([record, {"type": "resource", "rid": 1, "amount": 7}]) == {1: 7}


@pytest.mark.parametrize("payload", [{"type": "resource", "rid": 1, "amount": 7}, "text", None, 5])
def test_a_payload_that_is_not_a_list_has_no_resources(payload: Any) -> None:
    assert resource_amounts(payload) == {}
