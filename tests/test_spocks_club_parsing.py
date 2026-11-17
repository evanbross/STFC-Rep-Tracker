# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-17
"""Pure tests for reading a Spock's Club export; no database or Flask needed."""
from datetime import UTC, datetime

import pytest

from app.spocks_club_parsing import (
    FactionReading,
    SpocksClubFormatError,
    export_time_from_filename,
    match_factions,
    parse_resource_amounts,
)

HEADER = "EntityId\tEntityType\tName\tDescription\tField\tValue"


def _export(*rows: str, bom: bool = True) -> str:
    """A small export in the real file's shape: BOM, CRLF line endings, tab-separated."""
    return ("﻿" if bom else "") + "\r\n".join((HEADER, *rows)) + "\r\n"


def test_reads_resource_amounts_by_id() -> None:
    text = _export(
        "970475396\tresource\tFederation Points\tRep.\tamount\t1048139084",
        "4135751670\tresource\tRomulan Points\t\tamount\t10000000",
    )

    assert parse_resource_amounts(text) == {970475396: 1048139084, 4135751670: 10000000}


def test_ignores_other_entity_types_and_fields() -> None:
    text = _export(
        "0\tbuilding\tOperations\tHQ\tlevel\t45",
        "13\tship\tEnterprise\t\ttier\t5",
        "970475396\tresource\tFederation Points\t\tamount\t7",
    )

    assert parse_resource_amounts(text) == {970475396: 7}


def test_quoted_description_with_tab_and_newline_does_not_shift_columns() -> None:
    text = _export(
        '1645812293\tresearch\tShip Commission\t"Rewards ""Botany Bay""\tblueprints.\r\nSecond line."\tlevel\t1',
        "598150761\tresource\tAugment Points\t\tamount\t20711798",
    )

    assert parse_resource_amounts(text) == {598150761: 20711798}


def test_without_bom_too() -> None:
    assert parse_resource_amounts(_export("1\tresource\tX\t\tamount\t2", bom=False)) == {1: 2}


def test_skips_non_numeric_resource_rows() -> None:
    text = _export("1\tresource\tX\t\tamount\tlots", "2\tresource\tY\t\tamount\t3")

    assert parse_resource_amounts(text) == {2: 3}


def test_missing_column_names_it() -> None:
    with pytest.raises(SpocksClubFormatError, match="EntityType"):
        parse_resource_amounts("EntityId\tName\tField\tValue\r\n1\tX\tamount\t2\r\n")


def test_not_a_tsv_at_all() -> None:
    with pytest.raises(SpocksClubFormatError):
        parse_resource_amounts("hello, world\n")


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        (
            "spocksclub-data-export_2026-11-13T01-13-36-913Z.tsv",
            datetime(2026, 11, 13, 1, 13, 36, 913000, tzinfo=UTC),
        ),
        ("spocksclub-data-export_2026-11-13T01-13-36Z.tsv", datetime(2026, 11, 13, 1, 13, 36, tzinfo=UTC)),
        ("spocksclub-data-export_2026-11-13T01-13-36-9Z.tsv", datetime(2026, 11, 13, 1, 13, 36, 900000, tzinfo=UTC)),
        ("spocksclub-data-export.tsv", None),
        ("spocksclub-data-export_2026-13-45T99-00-00Z.tsv", None),  # looks right, isn't a date
        (None, None),
    ],
)
def test_export_time_from_filename(filename: str | None, expected: datetime | None) -> None:
    assert export_time_from_filename(filename) == expected


def test_match_factions_reports_unmapped_and_missing() -> None:
    factions = [
        {"code": "FED", "name": "Federation", "spocks_resource_id": 970475396},
        {"code": "MAV", "name": "Maverick", "spocks_resource_id": None},
        {"code": "OLD", "name": "Old", "spocks_resource_id": 123},  # mapped, but not in this export
    ]

    readings, unmatched = match_factions(factions, {970475396: 5, 999: 1})

    assert readings == [FactionReading("FED", "Federation", 970475396, 5)]
    assert unmatched == ["Maverick", "Old"]
