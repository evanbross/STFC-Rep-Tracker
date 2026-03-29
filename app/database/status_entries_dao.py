from datetime import datetime, timezone
from typing import Any


class StatusEntriesDAO:
    def __init__(self, db) -> None:
        self.db = db

    def create_table(self, cursor):
        """Create status_entries table"""
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS status_entries
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           faction_id
                           INTEGER
                           NOT
                           NULL,
                           timestamp
                           TEXT
                           NOT
                           NULL,
                           value
                           INTEGER
                           NOT
                           NULL,
                           value_delta
                           INTEGER
                           DEFAULT 0,
                           FOREIGN
                           KEY
                       (
                           faction_id
                       ) REFERENCES factions
                       (
                           id
                       )
                           )
                       """)

    def add_status_entry(self, faction_name: str, value: int) -> dict[str, Any]:
        """Add a new stat entry for a faction"""
        with self.db.connect() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                           SELECT f.id
                           FROM factions f
                           WHERE f.name = ?
                           """,
                (faction_name,),
            )
            result = cursor.fetchone()

            if not result:
                raise ValueError(f"Faction '{faction_name}' not found")

            faction_id = result[0]

            timestamp = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                           INSERT INTO status_entries (faction_id, timestamp, value)
                           VALUES (?, ?, ?)
                           """,
                (faction_id, timestamp, value),
            )

            return {"faction_id": faction_id, "timestamp": timestamp, "value": value}

    def get_faction_entries(self, faction_name: str) -> list[dict[str, Any]]:
        """Get all stat entries for a specific faction"""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                           SELECT se.timestamp, se.value, se.value_delta, se.faction_id
                           FROM status_entries se
                                    JOIN factions f ON se.faction_id = f.id
                           WHERE f.name = ?
                           ORDER BY se.timestamp ASC
                           """,
                (faction_name,),
            )
            return [
                {
                    "timestamp": row[0],
                    "value": row[1],
                    "value_delta": row[2],
                    "faction_id": row[3],
                }
                for row in cursor.fetchall()
            ]

    _ALLOWED_SORT_COLUMNS = {
        "se.id",
        "se.faction_id",
        "se.timestamp",
        "se.value",
        "id",
        "faction_id",
        "timestamp",
        "value",
        "faction_name",
    }

    def get_all_entries(self, limit: int | None = None, offset: int | None = None, faction_name: str | None = None, sort: str | None = None) -> list[dict[str, Any]]:
        """Get all status entries, with optional filtering, sorting, and paging"""
        with self.db.connect() as conn:
            cursor = conn.cursor()

            query = """
                    SELECT se.id, se.faction_id, f.name AS faction_name, se.timestamp, se.value
                    FROM status_entries se
                             JOIN factions f ON se.faction_id = f.id
                    """
            params = []
            if faction_name is not None:
                query += " WHERE f.name = ?"
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
                query += " LIMIT ?"
                params.append(limit)
                if offset is not None:
                    query += " OFFSET ?"
                    params.append(offset)

            cursor.execute(query, params)

            return [
                {
                    "id": row[0],
                    "faction_id": row[1],
                    "faction_name": row[2],
                    "timestamp": row[3],
                    "value": row[4],
                }
                for row in cursor.fetchall()
            ]

    _ALLOWED_FACTION_SORT_COLUMNS = {"f.id", "f.name", "id", "name"}

    def get_all_entries_for_factions_summaries(
        self, faction_name=None, limit=None, offset=None, sort=None
    ):
        """Get all factions with their stat entries, with optional filtering, sorting, and paging"""
        with self.db.connect() as conn:
            cursor = conn.cursor()

            query = "SELECT f.id, f.name FROM factions f"
            params = []
            if faction_name is not None:
                query += " WHERE f.name = ?"
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
                query += " LIMIT ?"
                params.append(limit)
                if offset is not None:
                    query += " OFFSET ?"
                    params.append(offset)

            cursor.execute(query, params)
            factions = cursor.fetchall()

            result = {}
            for faction_id, name in factions:
                cursor.execute(
                    """
                               SELECT timestamp, value, faction_id
                               FROM status_entries
                               WHERE faction_id = ?
                               ORDER BY id DESC
                                   LIMIT 2
                               """,
                    (faction_id,),
                )
                rows = cursor.fetchall()
                entries = []
                if len(rows) >= 2:
                    latest_row = rows[0]
                    entries.append(
                        {
                            "timestamp": latest_row[0],
                            "value": latest_row[1],
                            "faction_id": latest_row[2],
                        }
                    )
                result[name] = entries

            return result
