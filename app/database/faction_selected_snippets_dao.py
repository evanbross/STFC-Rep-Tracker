# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
from dataclasses import dataclass
from typing import Any

import psycopg2.errors

from app.domain_errors import NotFoundError


# ai: claude-opus-5-5 | 2026-11-18
@dataclass(frozen=True)
class DeletedSnippet:
    """What a deleted row leaves behind.

    remove_file is True only for an uploaded image that no other snippet row or
    faction column still names, so the caller may delete it from the user folder.
    """

    filename: str
    remove_file: bool


class FactionSelectedSnippetsDAO:
    def __init__(self, db: Any) -> None:
        self.db = db

    # ai: claude-opus-5-5 | 2026-11-18
    def get_snippets_for_faction(self, faction_id: str, snippet_type: str | None = None) -> list[dict[str, Any]]:
        """Return a faction's snippet rows, optionally filtered by type."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            if snippet_type:
                cursor.execute(
                    "SELECT id, filename, snippet_type, uploaded FROM faction_selected_snippets "
                    "WHERE faction_id = %s AND snippet_type = %s",
                    (faction_id, snippet_type),
                )
            else:
                cursor.execute(
                    "SELECT id, filename, snippet_type, uploaded FROM faction_selected_snippets "
                    "WHERE faction_id = %s",
                    (faction_id,),
                )
            return [
                {"id": r[0], "filename": r[1], "snippet_type": r[2], "uploaded": r[3]}
                for r in cursor.fetchall()
            ]

    # ai: claude-opus-5-5 | 2026-11-18
    def add_snippet(
        self, faction_id: str, filename: str, snippet_type: str | None = None, *, uploaded: bool = False
    ) -> int:
        """Add a snippet filename for a faction and return the new row id.

        `uploaded` marks an image the API wrote to the user folder. Raises
        NotFoundError if the faction does not exist.
        """
        with self.db.connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO faction_selected_snippets (faction_id, filename, snippet_type, uploaded) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    (faction_id, filename, snippet_type, uploaded),
                )
            except psycopg2.errors.ForeignKeyViolation as exc:
                raise NotFoundError(f"Faction '{faction_id}' not found") from exc
            return cursor.fetchone()[0]

    # ai: claude-opus-5-5 | 2026-11-18
    def delete_snippet(self, snippet_id: int) -> DeletedSnippet | None:
        """Delete a snippet row; None if there was no such row.

        The reference check runs in the same transaction as the delete, so it
        sees the table without this row.
        """
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM faction_selected_snippets WHERE id = %s RETURNING filename, uploaded",
                (snippet_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            filename, uploaded = row
            if not uploaded:
                return DeletedSnippet(filename, remove_file=False)
            cursor.execute(
                """
                SELECT EXISTS (SELECT 1 FROM faction_selected_snippets WHERE filename = %(name)s)
                    OR EXISTS (
                        SELECT 1 FROM factions
                        WHERE snippet_selected_button = %(name)s OR snippet_unselected = %(name)s
                    )
                """,
                {"name": filename},
            )
            still_used = cursor.fetchone()[0]
            return DeletedSnippet(filename, remove_file=not still_used)
