import logging
import sqlite3
from datetime import datetime

from app.app_config import capture_cfg
from app.database import reputations_dao

logger = logging.getLogger(__name__)


class FactionsDAO:
    def __init__(self, db):
        self.db = db

    def create_table(self, cursor):
        """Create factions table and handle migrations"""
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS factions
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           name
                           TEXT
                           NOT
                           NULL
                           UNIQUE,
                           on_chart
                           INTEGER
                           NOT
                           NULL
                           DEFAULT
                           0,
                           display_order
                           INTEGER,
                           code
                           TEXT,
                           color
                           TEXT,
                           reputation_table_name
                           TEXT,
                           reputation_dao_name
                           TEXT,
                           snippet_selected_button
                           TEXT,
                           snippet_unselected
                           TEXT
                       )
                       """)

        # Ensure required columns exist for existing databases
        cursor.execute("PRAGMA table_info('factions')")
        columns = [row[1] for row in cursor.fetchall()]
        if "on_chart" not in columns:
            cursor.execute(
                "ALTER TABLE factions ADD COLUMN on_chart INTEGER NOT NULL DEFAULT 0"
            )
        if "display_order" not in columns:
            cursor.execute("ALTER TABLE factions ADD COLUMN display_order INTEGER")
        if "code" not in columns:
            cursor.execute("ALTER TABLE factions ADD COLUMN code TEXT")
        if "color" not in columns:
            cursor.execute("ALTER TABLE factions ADD COLUMN color TEXT")
        if "reputation_table_name" not in columns:
            cursor.execute("ALTER TABLE factions ADD COLUMN reputation_table_name TEXT")
        if "reputation_dao_name" not in columns:
            cursor.execute("ALTER TABLE factions ADD COLUMN reputation_dao_name TEXT")
        # Rename old columns if they exist (SQLite 3.25+)
        # snippet_selected → snippet_selected_button
        if (
            "snippet_selected_button_button" in columns
            and "snippet_selected_button" not in columns
        ):
            # Fix earlier double-rename corruption
            cursor.execute(
                "ALTER TABLE factions RENAME COLUMN snippet_selected_button_button TO snippet_selected_button"
            )
        elif "snippet_selected" in columns and "snippet_selected_button" not in columns:
            cursor.execute(
                "ALTER TABLE factions RENAME COLUMN snippet_selected TO snippet_selected_button"
            )
        elif "snippet_selected_button" not in columns:
            cursor.execute(
                "ALTER TABLE factions ADD COLUMN snippet_selected_button TEXT"
            )
        # Drop legacy snippet_selected_desc — data now lives in faction_selected_snippets
        if "snippet_selected_desc" in columns or "snippet_selected_2" in columns:
            try:
                old = (
                    "snippet_selected_2"
                    if "snippet_selected_2" in columns
                    else "snippet_selected_desc"
                )
                if old == "snippet_selected_2":
                    cursor.execute(
                        "ALTER TABLE factions RENAME COLUMN snippet_selected_2 TO snippet_selected_desc"
                    )
                cursor.execute("ALTER TABLE factions DROP COLUMN snippet_selected_desc")
            except Exception as e:
                logger.warning(f"Could not drop legacy snippet_selected_desc column (SQLite < 3.35): {e}")
        if "snippet_unselected" not in columns:
            cursor.execute("ALTER TABLE factions ADD COLUMN snippet_unselected TEXT")
        cursor.execute("""
            UPDATE factions
            SET snippet_unselected = 'RepButton' || upper(substr(code, 1, 1)) || lower(substr(code, 2)) || '.jpg'
            WHERE snippet_unselected IS NULL AND code IS NOT NULL
        """)

    def get_all_factions(self):
        """Get list of all factions with their selected snippets."""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                           SELECT f.id, f.name, f.code, f.on_chart, f.color, f.reputation_table_name, f.display_order, f.reputation_dao_name, f.snippet_selected_button, f.snippet_unselected
                           FROM factions f
                           ORDER BY f.display_order
                           """)
            rows = cursor.fetchall()

            cursor.execute("""
                           SELECT faction_id, id, filename, snippet_type
                           FROM faction_selected_snippets
                           ORDER BY faction_id, snippet_type, filename
                           """)
            snippets_by_faction = {}
            for r in cursor.fetchall():
                snippets_by_faction.setdefault(r[0], []).append(
                    {"id": r[1], "filename": r[2], "snippet_type": r[3]}
                )

            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "code": row[2],
                    "on_chart": row[3],
                    "color": row[4],
                    "reputation_table_name": row[5],
                    "display_order": row[6],
                    "reputation_dao_name": row[7],
                    "snippet_selected_button": row[8],
                    "snippet_unselected": row[9],
                    "faction_type": row[2],
                    "selected_snippets": snippets_by_faction.get(row[0], []),
                }
                for row in rows
            ]
        finally:
            conn.close()

    def add_faction(
        self,
        name,
        code,
        color=None,
        reputation_table_name=None,
        on_chart=0,
        display_order=None,
        reputation_dao_name=None,
        snippet_selected_button=None,
        snippet_unselected=None,
    ):
        """Add a new faction"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                               INSERT INTO factions (name, code, color, reputation_table_name, on_chart, display_order, reputation_dao_name, snippet_selected_button, snippet_unselected)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                               """,
                    (
                        name,
                        code,
                        color,
                        reputation_table_name,
                        on_chart,
                        display_order,
                        reputation_dao_name,
                        snippet_selected_button,
                        snippet_unselected,
                    ),
                )
            except sqlite3.IntegrityError:
                raise ValueError(f"Faction with name '{name}' already exists")

            faction_id = cursor.lastrowid
            conn.commit()

            return {
                "id": faction_id,
                "name": name,
                "code": code,
                "color": color,
                "reputation_table_name": reputation_table_name,
                "on_chart": on_chart,
                "display_order": display_order,
                "reputation_dao_name": reputation_dao_name,
                "snippet_selected_button": snippet_selected_button,
                "snippet_unselected": snippet_unselected,
            }
        finally:
            conn.close()

    def update_faction(
        self,
        id,
        name,
        code,
        color=None,
        reputation_table_name=None,
        on_chart=0,
        display_order=None,
        reputation_dao_name=None,
        snippet_selected_button=None,
        snippet_unselected=None,
    ):
        """Update an existing faction"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()

            # Check if faction exists
            cursor.execute("SELECT id FROM factions WHERE id = ?", (id,))
            if not cursor.fetchone():
                raise ValueError(f"Faction with id {id} not found")

            try:
                cursor.execute(
                    """
                               UPDATE factions
                               SET name                  = ?,
                                   code                  = ?,
                                   color                 = ?,
                                   reputation_table_name = ?,
                                   on_chart              = ?,
                                   display_order         = ?,
                                   reputation_dao_name   = ?,
                                   snippet_selected_button      = ?,
                                   snippet_unselected    = ?
                               WHERE id = ?
                               """,
                    (
                        name,
                        code,
                        color,
                        reputation_table_name,
                        on_chart,
                        display_order,
                        reputation_dao_name,
                        snippet_selected_button,
                        snippet_unselected,
                        id,
                    ),
                )
            except sqlite3.IntegrityError:
                raise ValueError(f"Faction with name '{name}' already exists")

            conn.commit()

            return {
                "id": id,
                "name": name,
                "code": code,
                "color": color,
                "reputation_table_name": reputation_table_name,
                "on_chart": on_chart,
                "display_order": display_order,
                "reputation_dao_name": reputation_dao_name,
                "snippet_selected_button": snippet_selected_button,
                "snippet_unselected": snippet_unselected,
            }
        finally:
            conn.close()

    def get_faction_names(self):
        """Get a list of all faction names ordered by display_order"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM factions ORDER BY display_order")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_faction_summary(self, sort_by=None):
        """Get summary data for all factions including latest value and delta"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                           SELECT f.id, f.name, f.code, f.on_chart, f.color, f.reputation_table_name, f.display_order, f.reputation_dao_name
                           FROM factions f
                           ORDER BY f.display_order
                           """)
            factions_list = cursor.fetchall()

            result = []
            for (
                faction_id,
                name,
                faction_type_code,
                on_chart,
                color,
                reputation_table_name,
                display_order,
                reputation_dao_name,
            ) in factions_list:

                avg_entries = capture_cfg("factions", "avg_entries", default=5)
                cursor.execute(
                    f"""
                               SELECT value, timestamp
                               FROM status_entries
                               WHERE faction_id = ?
                               ORDER BY timestamp DESC
                                   LIMIT {int(avg_entries)}
                               """,
                    (faction_id,),
                )

                entries = cursor.fetchall()
                latest = entries[0] if len(entries) > 0 else None
                previous = entries[1] if len(entries) > 1 else None

                # Get total count of entries
                cursor.execute(
                    """
                               SELECT COUNT(*)
                               FROM status_entries
                               WHERE faction_id = ?
                               """,
                    (faction_id,),
                )
                entry_count = cursor.fetchone()[0]

                # Calculate status
                status = {
                    "time_delta": 0,
                    "value_delta": 0,
                    "raw_value_delta_per_minute": 0.0,
                    "avg_value_delta_per_minute": 0.0,
                    "minutes_to_goal": 0.0,
                    "reputation_level": "Unknown",
                }

                current_value = latest[0] if latest else 0

                rep_level = "Unknown"
                value_delta = 0
                if latest and previous:
                    # get the appropriate reputation DAO for this faction
                    rep_dao = reputations_dao.ReputationsDAO.get_dao_by_faction_name(name)
                    if rep_dao is None:
                        rep_dao = reputations_dao.ReputationsDAO(
                            conn, reputation_table_name
                        )
                    reputation_row = rep_dao.find_reputation_by_value(conn, latest[0])

                    # get the time delta in minutes
                    t1 = datetime.fromisoformat(previous[1])
                    t2 = datetime.fromisoformat(latest[1])
                    time_diff_mins = (t2 - t1).total_seconds() / 60
                    value_delta = latest[0] - previous[0]
                    rep_level = reputation_row[0] if reputation_row else "Unknown"
                    raw_value_delta_per_minute = value_delta / time_diff_mins

                    # Average rate across the full retrieved window (first vs last entry)
                    oldest = entries[-1]
                    avg_span_mins = (t2 - datetime.fromisoformat(oldest[1])).total_seconds() / 60
                    avg_value_delta_per_minute = (
                        (latest[0] - oldest[0]) / avg_span_mins
                        if avg_span_mins > 0
                        else raw_value_delta_per_minute
                    )

                    if time_diff_mins > 0:
                        status["time_delta"] = time_diff_mins
                        status["value_delta"] = value_delta
                        status["raw_value_delta_per_minute"] = raw_value_delta_per_minute
                        status["avg_value_delta_per_minute"] = avg_value_delta_per_minute

                        # Calculate minutes to goal
                        if reputation_row is not None:
                            status["reputation_level"] = reputation_row[0]
                            status["next_rep_level"] = rep_dao.find_next_reputation_name(
                                conn, reputation_row[2]
                            )
                            if (
                                avg_value_delta_per_minute > 0
                                and reputation_row[2] is not None
                            ):
                                dist = reputation_row[2] - current_value
                                status["minutes_to_goal"] = round(
                                    dist / avg_value_delta_per_minute, 2
                                )
                                status["minutes"] = status["minutes_to_goal"]
                        else:
                            status["minutes_to_goal"] = 0.0
                            status["minutes"] = 0.0

                result.append(
                    {
                        "id": faction_id,
                        "name": name,
                        "faction_type": faction_type_code,
                        "on_chart": on_chart,
                        "display_order": display_order,
                        "reputation_table_name": reputation_table_name,
                        "reputation_dao_name": reputation_dao_name,
                        "color": color,
                        "current_value": current_value,
                        "rep_level": rep_level,
                        "last_delta": value_delta,
                        "last_updated": latest[1] if latest else None,
                        "entry_count": entry_count,
                        "status": status,
                    }
                )
        finally:
            conn.close()

        if sort_by:
            reverse = False
            if sort_by.startswith("-"):
                reverse = True
                sort_by = sort_by[1:]

            if sort_by == "name":
                result.sort(key=lambda x: x["name"].lower(), reverse=reverse)
            elif sort_by == "display_order":
                result.sort(
                    key=lambda x: (
                        x["display_order"] if x["display_order"] is not None else 999999
                    ),
                    reverse=reverse,
                )
            elif sort_by == "current_value":
                result.sort(key=lambda x: x["current_value"], reverse=reverse)
            elif sort_by == "last_delta":
                result.sort(key=lambda x: x["last_delta"], reverse=reverse)
            elif sort_by == "remaining_time":
                result.sort(key=lambda x: x["status"]["minutes"], reverse=reverse)
            elif sort_by == "change_rate":
                result.sort(
                    key=lambda x: x["status"]["raw_value_delta_per_minute"], reverse=reverse
                )
            elif sort_by == "rep_level":
                result.sort(key=lambda x: x["rep_level"].lower(), reverse=reverse)
            elif sort_by == "last_updated":
                result.sort(key=lambda x: x["last_updated"] or "", reverse=reverse)
            elif sort_by == "entry_count":
                result.sort(key=lambda x: x["entry_count"], reverse=reverse)

        return result
