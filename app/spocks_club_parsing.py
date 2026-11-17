# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-17
"""Read faction reputation out of a Spock's Club data export (a leaf module).

The export is a long-format TSV, one row per entity field:

    EntityId  EntityType  Name  Description  Field  Value

Faction reputation is stored as a resource: EntityType "resource", Field
"amount", with the game's resource ID in EntityId (e.g. 970475396 is
"Federation Points"). Names repeat across resources ("Battle Pass Points"
appears a dozen times), so factions are matched by ID, never by name.
"""
import csv
import io
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

REQUIRED_COLUMNS = frozenset({"EntityId", "EntityType", "Field", "Value"})

# Spock's Club names the file after the export instant when it can, e.g.
# spocksclub-data-export_2026-11-13T01-13-36-913Z.tsv (colons become dashes).
_FILENAME_TIME = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})(?:-(\d{1,3}))?Z")


class SpocksClubFormatError(ValueError):
    """The upload isn't a Spock's Club export this parser understands. The message is shown to the user."""


@dataclass(frozen=True)
class FactionReading:
    faction_code: str
    faction_name: str
    resource_id: int
    value: int


def parse_resource_amounts(text: str) -> dict[int, int]:
    """Return {resource EntityId: amount} for every resource row with a whole-number amount.

    `text` is the decoded file. A leading byte-order mark is ignored, and quoted
    descriptions may contain tabs and newlines. Raises SpocksClubFormatError when
    the header lacks a required column.
    """
    reader = csv.DictReader(io.StringIO(text.removeprefix("﻿")), delimiter="\t")
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
    if missing:
        raise SpocksClubFormatError(
            "This doesn't look like a Spock's Club data export: it has no "
            f"{', '.join(sorted(missing))} column. Export the TSV from Spock's Club and try again."
        )

    amounts: dict[int, int] = {}
    for row in reader:
        if row["EntityType"] != "resource" or row["Field"] != "amount":
            continue
        try:
            amounts[int(row["EntityId"])] = int(row["Value"])
        except (TypeError, ValueError):
            continue  # a non-numeric resource row is not one we can use
    return amounts


def export_time_from_filename(filename: str | None) -> datetime | None:
    """The export instant encoded in a Spock's Club filename, in UTC, or None if it has none."""
    match = _FILENAME_TIME.search(filename or "")
    if match is None:
        return None
    day, hours, minutes, seconds, millis = match.groups()
    try:
        moment = datetime.fromisoformat(f"{day}T{hours}:{minutes}:{seconds}")
    except ValueError:
        return None
    millis_value = int((millis or "0").ljust(3, "0"))
    return moment.replace(microsecond=millis_value * 1000, tzinfo=UTC)


def match_factions(
    factions: list[dict[str, Any]], amounts: dict[int, int]
) -> tuple[list[FactionReading], list[str]]:
    """Pair factions with their exported amounts.

    `factions` are dicts with code, name and spocks_resource_id. Returns
    (readings, unmatched faction names): a faction is unmatched when it has no
    resource ID or the export has no amount for it.
    """
    readings: list[FactionReading] = []
    unmatched: list[str] = []
    for faction in factions:
        resource_id = faction.get("spocks_resource_id")
        if resource_id is None or resource_id not in amounts:
            unmatched.append(faction["name"])
            continue
        readings.append(
            FactionReading(faction["code"], faction["name"], resource_id, amounts[resource_id])
        )
    return readings, unmatched
