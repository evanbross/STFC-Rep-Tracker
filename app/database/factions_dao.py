import sqlite3
from datetime import datetime

from app.database import reputations_dao


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
                           snippet_selected_desc
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
        if "snippet_selected_button_button" in columns and "snippet_selected_button" not in columns:
            # Fix earlier double-rename corruption
            cursor.execute("ALTER TABLE factions RENAME COLUMN snippet_selected_button_button TO snippet_selected_button")
        elif "snippet_selected" in columns and "snippet_selected_button" not in columns:
            cursor.execute("ALTER TABLE factions RENAME COLUMN snippet_selected TO snippet_selected_button")
        elif "snippet_selected_button" not in columns:
            cursor.execute("ALTER TABLE factions ADD COLUMN snippet_selected_button TEXT")
        # snippet_selected_2 → snippet_selected_desc
        if "snippet_selected_2" in columns and "snippet_selected_desc" not in columns:
            cursor.execute("ALTER TABLE factions RENAME COLUMN snippet_selected_2 TO snippet_selected_desc")
        elif "snippet_selected_desc" not in columns:
            cursor.execute("ALTER TABLE factions ADD COLUMN snippet_selected_desc TEXT")
        if "snippet_unselected" not in columns:
            cursor.execute("ALTER TABLE factions ADD COLUMN snippet_unselected TEXT")
        cursor.execute("""
            UPDATE factions
            SET snippet_unselected = 'RepButton' || upper(substr(code, 1, 1)) || lower(substr(code, 2)) || '.jpg'
            WHERE snippet_unselected IS NULL AND code IS NOT NULL
        """)

    def get_all_factions(self):
        """Get list of all factions"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       SELECT f.id, f.name, f.code, f.on_chart, f.color, f.reputation_table_name, f.display_order, f.reputation_dao_name, f.snippet_selected_button, f.snippet_selected_desc, f.snippet_unselected
                       FROM factions f
                       ORDER BY f.display_order
                       """)
        factions = [
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
                "snippet_selected_desc": row[9],
                "snippet_unselected": row[10],
                "faction_type": row[2],  # Map code to faction_type for compatibility
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return factions

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
        snippet_selected_desc=None,
        snippet_unselected=None,
    ):
        """Add a new faction"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                           INSERT INTO factions (name, code, color, reputation_table_name, on_chart, display_order, reputation_dao_name, snippet_selected_button, snippet_selected_desc, snippet_unselected)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    snippet_selected_desc,
                    snippet_unselected,
                ),
            )

            faction_id = cursor.lastrowid
            conn.commit()

            result = {
                "id": faction_id,
                "name": name,
                "code": code,
                "color": color,
                "reputation_table_name": reputation_table_name,
                "on_chart": on_chart,
                "display_order": display_order,
                "reputation_dao_name": reputation_dao_name,
                "snippet_selected_button": snippet_selected_button,
                "snippet_selected_desc": snippet_selected_desc,
                "snippet_unselected": snippet_unselected,
            }
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Faction with name '{name}' already exists")
        except Exception as e:
            conn.close()
            raise e

        conn.close()
        return result

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
        snippet_selected_desc=None,
        snippet_unselected=None,
    ):
        """Update an existing faction"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Check if faction exists
        cursor.execute("SELECT id FROM factions WHERE id = ?", (id,))
        if not cursor.fetchone():
            conn.close()
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
                               snippet_selected_desc    = ?,
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
                    snippet_selected_desc,
                    snippet_unselected,
                    id,
                ),
            )

            conn.commit()

            result = {
                "id": id,
                "name": name,
                "code": code,
                "color": color,
                "reputation_table_name": reputation_table_name,
                "on_chart": on_chart,
                "display_order": display_order,
                "reputation_dao_name": reputation_dao_name,
                "snippet_selected_button": snippet_selected_button,
                "snippet_selected_desc": snippet_selected_desc,
                "snippet_unselected": snippet_unselected,
            }
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Faction with name '{name}' already exists")
        except Exception as e:
            conn.close()
            raise e

        conn.close()
        return result

    def get_faction_names(self):
        """Get a list of all faction names ordered by display_order"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM factions ORDER BY display_order")
        names = [row[0] for row in cursor.fetchall()]
        conn.close()
        return names

    def get_faction_summary(self, sort_by=None):
        """Get summary data for all factions including latest value and delta"""
        conn = self.db.get_connection()
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

            # Get latest entries (up to 2 for calculation)
            cursor.execute(
                """
                           SELECT value, timestamp
                           FROM status_entries
                           WHERE faction_id = ?
                           ORDER BY timestamp DESC
                               LIMIT 2
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
                    rep_dao = reputations_dao.ReputationsDAO(conn, reputation_table_name)
                reputation_row = rep_dao.find_reputation_by_value(conn, latest[0])

                # get the time delta in minutes
                t1 = datetime.fromisoformat(previous[1])
                t2 = datetime.fromisoformat(latest[1])
                time_diff_mins = (t2 - t1).total_seconds() / 60
                value_delta = latest[0] - previous[0]
                rep_level = reputation_row[0] if reputation_row else "Unknown"
                raw_value_delta_per_minute = value_delta / time_diff_mins
                avg_value_delta_per_minute = value_delta / time_diff_mins

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
                    key=lambda x: x["status"]["raw_change_per_minute"], reverse=reverse
                )
            elif sort_by == "rep_level":
                result.sort(key=lambda x: x["rep_level"].lower(), reverse=reverse)
            elif sort_by == "last_updated":
                result.sort(key=lambda x: x["last_updated"] or "", reverse=reverse)
            elif sort_by == "entry_count":
                result.sort(key=lambda x: x["entry_count"], reverse=reverse)

        return result
