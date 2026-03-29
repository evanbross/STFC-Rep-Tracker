class FactionSelectedSnippetsDAO:
    def __init__(self, db):
        self.db = db

    def create_table(self, cursor):
        """Create faction_selected_snippets table and seed from legacy columns."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faction_selected_snippets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                faction_id  INTEGER NOT NULL,
                filename    TEXT    NOT NULL,
                snippet_type TEXT,
                FOREIGN KEY (faction_id) REFERENCES factions(id)
            )
        """)

        # Migrate legacy snippet_selected_button column into the new table
        cursor.execute("""
            INSERT INTO faction_selected_snippets (faction_id, filename, snippet_type)
            SELECT id, snippet_selected_button, 'button'
            FROM factions
            WHERE snippet_selected_button IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM faction_selected_snippets fss
                WHERE fss.faction_id = factions.id
                  AND fss.filename = factions.snippet_selected_button
              )
        """)

    def get_snippets_for_faction(self, faction_id, snippet_type=None):
        """Return list of filenames for a faction, optionally filtered by type."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            if snippet_type:
                cursor.execute(
                    "SELECT id, filename, snippet_type FROM faction_selected_snippets "
                    "WHERE faction_id = ? AND snippet_type = ?",
                    (faction_id, snippet_type),
                )
            else:
                cursor.execute(
                    "SELECT id, filename, snippet_type FROM faction_selected_snippets "
                    "WHERE faction_id = ?",
                    (faction_id,),
                )
            return [{"id": r[0], "filename": r[1], "snippet_type": r[2]} for r in cursor.fetchall()]

    def get_all_snippets(self):
        """Return all rows grouped by faction_id."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, faction_id, filename, snippet_type "
                "FROM faction_selected_snippets ORDER BY faction_id, snippet_type, filename"
            )
            return [
                {"id": r[0], "faction_id": r[1], "filename": r[2], "snippet_type": r[3]}
                for r in cursor.fetchall()
            ]

    def add_snippet(self, faction_id, filename, snippet_type=None):
        """Add a snippet filename for a faction. Returns the new row id."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO faction_selected_snippets (faction_id, filename, snippet_type) "
                "VALUES (?, ?, ?)",
                (faction_id, filename, snippet_type),
            )
            return cursor.lastrowid

    def delete_snippet(self, snippet_id):
        """Delete a snippet row by id. Returns True if a row was deleted."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM faction_selected_snippets WHERE id = ?", (snippet_id,))
            return cursor.rowcount > 0

    def set_snippets_for_faction(self, faction_id, filenames_by_type):
        """Replace all snippets for a faction.

        filenames_by_type: list of {"filename": str, "snippet_type": str|None}
        """
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM faction_selected_snippets WHERE faction_id = ?", (faction_id,)
            )
            for entry in filenames_by_type:
                cursor.execute(
                    "INSERT INTO faction_selected_snippets (faction_id, filename, snippet_type) "
                    "VALUES (?, ?, ?)",
                    (faction_id, entry["filename"], entry.get("snippet_type")),
                )
