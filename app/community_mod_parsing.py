# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-19
"""Read resource amounts out of a community-mod sync payload (a leaf module).

A payload is a JSON list of records, each tagged with a "type". Resources look
like {"type": "resource", "rid": 970475396, "amount": 1045097591}. The rid is
the same game resource ID a Spock's Club export uses as its EntityId (which is
where Spock's Club gets it from), so factions.spocks_resource_id matches both.

A full sync sends every resource (about 5,700); a change sends only the
resources that changed. Other record types, and anything malformed, are ignored.
"""
from typing import Any

RESOURCE_TYPE = "resource"


def resource_amounts(payload: Any) -> dict[int, int]:
    """Return {rid: amount} for each well-formed resource record in `payload`.

    A payload that isn't a list (the mod sends some objects too) has none. When
    a rid appears twice, the later record wins, as it's the newer value.
    """
    if not isinstance(payload, list):
        return {}
    amounts: dict[int, int] = {}
    for record in payload:
        if not isinstance(record, dict) or record.get("type") != RESOURCE_TYPE:
            continue
        rid, amount = record.get("rid"), record.get("amount")
        if _is_int(rid) and _is_int(amount):
            amounts[rid] = amount
    return amounts


def _is_int(value: Any) -> bool:
    # bool is an int subclass, but true/false is never an ID or an amount.
    return isinstance(value, int) and not isinstance(value, bool)
