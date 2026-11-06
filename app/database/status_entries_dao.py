# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
from datetime import UTC, datetime
from typing import Any

from app.domain_errors import NotFoundError


# ai: claude-opus-5-5 | 2026-11-06
def iso_utc(moment: datetime) -> str:
    """Render a timestamptz value the way the API always has: ISO 8601 in UTC with an offset."""
    return moment.astimezone(UTC).isoformat()


class StatusEntriesDAO:
    def __init__(self, db: Any) -> None:
        self.db = db

    def add_status_entry(self, faction_name: str, value: int) -> dict[str, Any]:
        """Add a new stat entry for a faction"""
        with self.db.connect() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                           SELECT f.code
                           FROM factions f
                           WHERE f.name = %s
                           """,
                (faction_name,),
            )
            result = cursor.fetchone()

            if not result:
                raise NotFoundError(f"Faction '{faction_name}' not found")  # ai: claude-opus-5-5 | 2026-11-06

            faction_code = result[0]

            timestamp = datetime.now(UTC)  # ai: claude-opus-5-5 | 2026-11-06
            cursor.execute(
                """
                           INSERT INTO status_entries (faction_code, timestamp, value)
                           VALUES (%s, %s, %s)
                           """,
                (faction_code, timestamp, value),
            )

            return {"faction_code": faction_code, "timestamp": iso_utc(timestamp), "value": value}

    def get_faction_entries(self, faction_name: str) -> list[dict[str, Any]]:
        """Get all stat entries for a specific faction"""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                           SELECT se.timestamp, se.value, se.faction_code
                           FROM status_entries se
                                    JOIN factions f ON se.faction_code = f.code
                           WHERE f.name = %s
                           ORDER BY se.timestamp ASC
                           """,
                (faction_name,),
            )
            # ai: claude-opus-5-5 | 2026-11-06 — value_delta was never populated and is dropped (migration v2)
            return [
                {"timestamp": iso_utc(row[0]), "value": row[1], "faction_code": row[2]}
                for row in cursor.fetchall()
            ]

    _ALLOWED_SORT_COLUMNS = {
        "se.id",
        "se.faction_code",
        "se.timestamp",
        "se.value",
        "id",
        "faction_code",
        "timestamp",
        "value",
        "faction_name",
    }

    def get_all_entries(
        self,
        limit: int | None = None,
        offset: int | None = None,
        faction_name: str | None = None,
        sort: str | None = None,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get all status entries, with optional filtering, sorting, and paging.

        `since` keeps entries at or after that instant (N-P3: the Dashboard
        asks for a recent window instead of the whole history).
        """
        with self.db.connect() as conn:
            cursor = conn.cursor()

            query = """
                    SELECT se.id, se.faction_code, f.name AS faction_name, se.timestamp, se.value
                    FROM status_entries se
                             JOIN factions f ON se.faction_code = f.code
                    """
            params: list[Any] = []
            # ai: claude-opus-5-5 | 2026-11-06
            conditions: list[str] = []
            if faction_name is not None:
                conditions.append("f.name = %s")
                params.append(faction_name)
            if since is not None:
                conditions.append("se.timestamp >= %s")  # ai: claude-opus-5-5 | 2026-11-06
                params.append(since)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            if sort is not None:
                parts = sort.strip().split()
                column = parts[0].lower()
                direction = parts[1].upper() if len(parts) > 1 else "ASC"
                if column not in self._ALLOWED_SORT_COLUMNS or direction not in ("ASC", "DESC"):
                    raise ValueError(f"Invalid sort value: '{sort}'")
                query += f" ORDER BY {column} {direction}"
            else:
                query += " ORDER BY se.timestamp ASC"

            if limit is not None:
                query += " LIMIT %s"
                params.append(limit)
                if offset is not None:
                    query += " OFFSET %s"
                    params.append(offset)

            cursor.execute(query, params)

            return [
                {
                    "id": row[0],
                    "faction_code": row[1],
                    "faction_name": row[2],
                    "timestamp": iso_utc(row[3]),  # ai: claude-opus-5-5 | 2026-11-06
                    "value": row[4],
                }
                for row in cursor.fetchall()
            ]
