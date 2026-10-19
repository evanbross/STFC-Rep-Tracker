# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
from datetime import datetime, timezone
from typing import Any


class StatusEntriesDAO:
    def __init__(self, db: Any) -> None:
        self.db = db

    def create_table(self, cursor: Any) -> None:
        """Create status_entries table"""
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS status_entries
                       (
                           id           SERIAL PRIMARY KEY,
                           faction_code TEXT NOT NULL,
                           timestamp    TEXT NOT NULL,
                           value        INTEGER NOT NULL,
                           value_delta  INTEGER DEFAULT 0,
                           FOREIGN KEY (faction_code) REFERENCES factions(code) ON UPDATE CASCADE
                       )
                       """)

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
                raise ValueError(f"Faction '{faction_name}' not found")

            faction_code = result[0]

            timestamp = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                           INSERT INTO status_entries (faction_code, timestamp, value)
                           VALUES (%s, %s, %s)
                           """,
                (faction_code, timestamp, value),
            )

            return {"faction_code": faction_code, "timestamp": timestamp, "value": value}

    def get_faction_entries(self, faction_name: str) -> list[dict[str, Any]]:
        """Get all stat entries for a specific faction"""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                           SELECT se.timestamp, se.value, se.value_delta, se.faction_code
                           FROM status_entries se
                                    JOIN factions f ON se.faction_code = f.code
                           WHERE f.name = %s
                           ORDER BY se.timestamp ASC
                           """,
                (faction_name,),
            )
            return [
                {
                    "timestamp": row[0],
                    "value": row[1],
                    "value_delta": row[2],
                    "faction_code": row[3],
                }
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
    ) -> list[dict[str, Any]]:
        """Get all status entries, with optional filtering, sorting, and paging"""
        with self.db.connect() as conn:
            cursor = conn.cursor()

            query = """
                    SELECT se.id, se.faction_code, f.name AS faction_name, se.timestamp, se.value
                    FROM status_entries se
                             JOIN factions f ON se.faction_code = f.code
                    """
            params: list[Any] = []
            if faction_name is not None:
                query += " WHERE f.name = %s"
                params.append(faction_name)

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
                    "timestamp": row[3],
                    "value": row[4],
                }
                for row in cursor.fetchall()
            ]

    _ALLOWED_FACTION_SORT_COLUMNS = {"f.code", "f.name", "code", "name"}

    def get_all_entries_for_factions_summaries(
        self,
        faction_name: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Get all factions with their stat entries, with optional filtering, sorting, and paging"""
        with self.db.connect() as conn:
            cursor = conn.cursor()

            query = "SELECT f.code, f.name FROM factions f"
            params: list[Any] = []
            if faction_name is not None:
                query += " WHERE f.name = %s"
                params.append(faction_name)

            if sort is not None:
                parts = sort.strip().split()
                column = parts[0].lower()
                direction = parts[1].upper() if len(parts) > 1 else "ASC"
                if column not in self._ALLOWED_FACTION_SORT_COLUMNS or direction not in (
                    "ASC",
                    "DESC",
                ):
                    raise ValueError(f"Invalid sort value: '{sort}'")
                query += f" ORDER BY {column} {direction}"

            if limit is not None:
                query += " LIMIT %s"
                params.append(limit)
                if offset is not None:
                    query += " OFFSET %s"
                    params.append(offset)

            cursor.execute(query, params)
            factions = cursor.fetchall()

            result: dict[str, list[dict[str, Any]]] = {}
            for faction_code, name in factions:
                cursor.execute(
                    """
                               SELECT timestamp, value, faction_code
                               FROM status_entries
                               WHERE faction_code = %s
                               ORDER BY id DESC
                               LIMIT 2
                               """,
                    (faction_code,),
                )
                rows = cursor.fetchall()
                entries: list[dict[str, Any]] = []
                if rows:
                    # Always include the latest entry; a second row will be used for delta
                    # elsewhere (e.g. factions_dao._compute_faction_status).
                    # Factions with exactly one entry are included with no prior row to
                    # compare against — the caller is responsible for handling a missing
                    # second entry gracefully.
                    latest_row = rows[0]
                    entries.append(
                        {
                            "timestamp": latest_row[0],
                            "value": latest_row[1],
                            "faction_code": latest_row[2],
                        }
                    )
                result[name] = entries

            return result
