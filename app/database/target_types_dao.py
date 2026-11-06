# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
from __future__ import annotations

from typing import TYPE_CHECKING, Literal, get_args

if TYPE_CHECKING:
    from app.database.database import Database

# ai: claude-opus-5-5 | 2026-11-06
# Single source for preference values: request validation, the DAO guard, and
# the table's CHECK constraint all derive from this Literal.
TargetPreference = Literal["unknown", "target", "avoid"]
TARGET_PREFERENCES: tuple[str, ...] = get_args(TargetPreference)
_PREFERENCE_SQL_LIST = ", ".join(f"'{p}'" for p in TARGET_PREFERENCES)

_COLUMNS = (
    "id, system_name, template_filename, display_name, preference, "
    "sample_image_filename, example_name, example_level, times_seen, "
    "first_seen_at, last_seen_at"
)


def _row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "system_name": row[1],
        "template_filename": row[2],
        "display_name": row[3],
        "preference": row[4],
        "sample_image_filename": row[5],
        "example_name": row[6],
        "example_level": row[7],
        "times_seen": row[8],
        "first_seen_at": row[9].isoformat() if row[9] else None,
        "last_seen_at": row[10].isoformat() if row[10] else None,
    }


class TargetTypesDAO:
    """CRUD for the target_types table.

    Tracks every distinct hostile ship type (identified by which
    combat.hostile_ship_templates filename matched) seen in each system, and
    the user's target/avoid preference for it. A system with zero rows here
    has never been scanned; a system with any 'unknown' row still needs the
    user to finish classifying its roster before attack candidates are produced.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_table(self, cursor) -> None:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS target_types (
                id                    SERIAL PRIMARY KEY,
                system_name           TEXT NOT NULL,
                template_filename     TEXT NOT NULL,
                display_name          TEXT,
                preference            TEXT NOT NULL DEFAULT 'unknown'
                                          CHECK (preference IN ({_PREFERENCE_SQL_LIST})),
                sample_image_filename TEXT,
                example_name          TEXT,
                example_level         INTEGER,
                times_seen            INTEGER NOT NULL DEFAULT 1,
                first_seen_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_seen_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (system_name, template_filename)
            )
        """)

    def get_for_system(self, system_name: str) -> list[dict]:
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT {_COLUMNS} FROM target_types "
                "WHERE system_name = %s ORDER BY preference, display_name",
                (system_name,),
            )
            return [_row_to_dict(r) for r in cursor.fetchall()]

    def has_unclassified(self, system_name: str) -> bool:
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM target_types WHERE system_name = %s AND preference = 'unknown')",
                (system_name,),
            )
            return bool(cursor.fetchone()[0])

    def upsert_seen(
        self,
        system_name: str,
        template_filename: str,
        display_name: str | None = None,
        sample_image_filename: str | None = None,
        example_name: str | None = None,
        example_level: int | None = None,
    ) -> dict:
        """Record a sighting of this type in this system.

        On first sighting, inserts a new 'unknown'-preference row with the
        given display name / sample / example. On a repeat sighting, only
        bumps times_seen/last_seen_at — the originally captured sample image
        and example name/level are kept rather than overwritten, and the
        preference (and any user-edited display_name) is left untouched.
        """
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                INSERT INTO target_types
                    (system_name, template_filename, display_name,
                     sample_image_filename, example_name, example_level)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (system_name, template_filename) DO UPDATE SET
                    times_seen   = target_types.times_seen + 1,
                    last_seen_at = NOW()
                RETURNING {_COLUMNS}
                """,
                (system_name, template_filename, display_name, sample_image_filename, example_name, example_level),
            )
            row = cursor.fetchone()
        return _row_to_dict(row)

    def set_preference(self, type_id: int, preference: str, display_name: str | None = None) -> dict | None:
        """Update a type's target/avoid/unknown preference, and optionally rename it."""
        if preference not in TARGET_PREFERENCES:
            raise ValueError(f"Invalid preference: {preference!r}")
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                UPDATE target_types
                SET preference = %s, display_name = COALESCE(%s, display_name)
                WHERE id = %s
                RETURNING {_COLUMNS}
                """,
                (preference, display_name, type_id),
            )
            row = cursor.fetchone()
        return _row_to_dict(row) if row else None
