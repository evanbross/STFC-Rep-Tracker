from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.database.database import Database


class TerritorySystemsDAO:
    """CRUD for the territory_systems table.

    Stores the weekly capture schedule for each alliance territory system:
    which day of the week (0=Monday … 6=Sunday) and what local time the
    event fires.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_table(self, cursor) -> None:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS territory_systems (
                id          SERIAL PRIMARY KEY,
                name        VARCHAR(100) UNIQUE NOT NULL,
                day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
                event_time  TIME NOT NULL
            )
        """)

    def get_all(self) -> list[dict]:
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, day_of_week, TO_CHAR(event_time, 'HH24:MI')
                FROM territory_systems
                ORDER BY day_of_week, event_time
            """)
            return [
                {"id": r[0], "name": r[1], "day_of_week": r[2], "event_time": r[3]}
                for r in cursor.fetchall()
            ]

    def upsert(self, name: str, day_of_week: int, event_time: str) -> dict:
        """Insert or update a system by name. Returns the saved row."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO territory_systems (name, day_of_week, event_time)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    day_of_week = EXCLUDED.day_of_week,
                    event_time  = EXCLUDED.event_time
                RETURNING id, name, day_of_week, TO_CHAR(event_time, 'HH24:MI')
            """, (name, day_of_week, event_time))
            row = cursor.fetchone()
        return {"id": row[0], "name": row[1], "day_of_week": row[2], "event_time": row[3]}

    def update(self, system_id: int, name: str, day_of_week: int, event_time: str) -> dict | None:
        """Update an existing system by ID. Returns the updated row, or None if not found."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE territory_systems
                SET name = %s, day_of_week = %s, event_time = %s
                WHERE id = %s
                RETURNING id, name, day_of_week, TO_CHAR(event_time, 'HH24:MI')
            """, (name, day_of_week, event_time, system_id))
            row = cursor.fetchone()
        if not row:
            return None
        return {"id": row[0], "name": row[1], "day_of_week": row[2], "event_time": row[3]}

    def delete(self, system_id: int) -> bool:
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM territory_systems WHERE id = %s", (system_id,))
            return cursor.rowcount > 0