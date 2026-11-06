# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
from datetime import datetime
from typing import Any

import psycopg2.errors

from app.app_config import capture_cfg
from app.database import reputations_dao
from app.domain_errors import ConflictError, NotFoundError


class FactionsDAO:
    def __init__(self, db) -> None:
        self.db = db

    def create_table(self, cursor):
        """Create the current factions table schema."""
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS factions
                       (
                           code                    TEXT PRIMARY KEY,
                           name                    TEXT NOT NULL UNIQUE,
                           on_chart                INTEGER NOT NULL DEFAULT 0,
                           display_order           INTEGER,
                           color                   TEXT,
                           reputation_table_name   TEXT,
                           reputation_dao_name     TEXT,
                           snippet_selected_button TEXT,
                           snippet_unselected      TEXT
                       )
                       """)
        cursor.execute("""
            UPDATE factions
            SET snippet_unselected = 'RepButton' || upper(substr(code, 1, 1)) || lower(substr(code, 2)) || '.jpg'
            WHERE snippet_unselected IS NULL AND code IS NOT NULL
        """)

    @staticmethod
    def _row_to_dict(row, selected_snippets) -> dict[str, Any]:
        """Convert a factions SELECT row (9-column tuple) to a faction dict.

        Column order: code, name, on_chart, color, reputation_table_name,
                      display_order, reputation_dao_name, snippet_selected_button,
                      snippet_unselected
        """
        code = row[0]
        return {
            "id": code,   # backward-compat alias — value is the code string
            "code": code,
            "name": row[1],
            "on_chart": row[2],
            "color": row[3],
            "reputation_table_name": row[4],
            "display_order": row[5],
            "reputation_dao_name": row[6],
            "snippet_selected_button": row[7],
            "snippet_unselected": row[8],
            "faction_type": code,
            "selected_snippets": selected_snippets,
        }

    @staticmethod
    def _params_to_dict(code, name, color, reputation_table_name, on_chart,
                        display_order, reputation_dao_name, snippet_selected_button,
                        snippet_unselected) -> dict[str, Any]:
        """Build a faction response dict from individual field values."""
        return {
            "id": code,   # backward-compat alias
            "code": code,
            "name": name,
            "color": color,
            "reputation_table_name": reputation_table_name,
            "on_chart": on_chart,
            "display_order": display_order,
            "reputation_dao_name": reputation_dao_name,
            "snippet_selected_button": snippet_selected_button,
            "snippet_unselected": snippet_unselected,
        }

    def get_all_factions_with_cursor(self, cursor: Any) -> list[dict[str, Any]]:
        """Get list of all factions with their selected snippets using an existing cursor."""
        cursor.execute("""
                       SELECT f.code, f.name, f.on_chart, f.color, f.reputation_table_name, f.display_order, f.reputation_dao_name, f.snippet_selected_button, f.snippet_unselected
                       FROM factions f
                       ORDER BY f.display_order
                       """)
        rows = cursor.fetchall()

        cursor.execute("""
                       SELECT faction_id, id, filename, snippet_type
                       FROM faction_selected_snippets
                       ORDER BY faction_id, snippet_type, filename
                       """)
        snippets_by_faction: dict[str, list] = {}
        for row in cursor.fetchall():
            snippets_by_faction.setdefault(row[0], []).append(
                {"id": row[1], "filename": row[2], "snippet_type": row[3]}
            )

        return [self._row_to_dict(row, snippets_by_faction.get(row[0], [])) for row in rows]

    def get_all_factions(self) -> list[dict[str, Any]]:
        """Get list of all factions with their selected snippets."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            return self.get_all_factions_with_cursor(cursor)

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
        with self.db.connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                               INSERT INTO factions (code, name, color, reputation_table_name, on_chart, display_order, reputation_dao_name, snippet_selected_button, snippet_unselected)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                               """,
                    (
                        code,
                        name,
                        color,
                        reputation_table_name,
                        on_chart,
                        display_order,
                        reputation_dao_name,
                        snippet_selected_button,
                        snippet_unselected,
                    ),
                )
            except psycopg2.errors.UniqueViolation as exc:
                raise ConflictError(f"Faction with name '{name}' or code '{code}' already exists") from exc  # ai: claude-opus-5-5 | 2026-11-06

            return self._params_to_dict(
                code, name, color, reputation_table_name, on_chart,
                display_order, reputation_dao_name, snippet_selected_button, snippet_unselected,
            )

    def update_faction(
        self,
        current_code,
        name,
        new_code,
        color=None,
        reputation_table_name=None,
        on_chart=0,
        display_order=None,
        reputation_dao_name=None,
        snippet_selected_button=None,
        snippet_unselected=None,
    ):
        """Update an existing faction identified by current_code."""
        with self.db.connect() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT code FROM factions WHERE code = %s", (current_code,))
            if not cursor.fetchone():
                raise NotFoundError(f"Faction with code '{current_code}' not found")  # ai: claude-opus-5-5 | 2026-11-06

            try:
                cursor.execute(
                    """
                               UPDATE factions
                               SET code                  = %s,
                                   name                  = %s,
                                   color                 = %s,
                                   reputation_table_name = %s,
                                   on_chart              = %s,
                                   display_order         = %s,
                                   reputation_dao_name   = %s,
                                   snippet_selected_button      = %s,
                                   snippet_unselected    = %s
                               WHERE code = %s
                               """,
                    (
                        new_code,
                        name,
                        color,
                        reputation_table_name,
                        on_chart,
                        display_order,
                        reputation_dao_name,
                        snippet_selected_button,
                        snippet_unselected,
                        current_code,
                    ),
                )
            except psycopg2.errors.UniqueViolation as exc:
                raise ConflictError(f"Faction with name '{name}' or code '{new_code}' already exists") from exc  # ai: claude-opus-5-5 | 2026-11-06

            return self._params_to_dict(
                new_code, name, color, reputation_table_name, on_chart,
                display_order, reputation_dao_name, snippet_selected_button, snippet_unselected,
            )

    def get_faction_by_code(self, faction_code: str):
        """Get a single faction by code with its selected snippets."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT f.code, f.name, f.on_chart, f.color, f.reputation_table_name, f.display_order, f.reputation_dao_name, f.snippet_selected_button, f.snippet_unselected
                FROM factions f
                WHERE f.code = %s
            """, (faction_code,))
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute("""
                SELECT id, filename, snippet_type
                FROM faction_selected_snippets
                WHERE faction_id = %s
                ORDER BY snippet_type, filename
            """, (faction_code,))
            snippets = [{"id": r[0], "filename": r[1], "snippet_type": r[2]} for r in cursor.fetchall()]
            return self._row_to_dict(row, snippets)

    def get_faction_names(self) -> list[str]:
        """Get a list of all faction names ordered by display_order"""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM factions ORDER BY display_order")
            return [row[0] for row in cursor.fetchall()]

    @staticmethod
    def _fetch_entries_and_count(cursor, faction_id):
        """Query recent status entries and total count for a faction."""
        avg_entries = capture_cfg("factions", "avg_entries", default=5)
        cursor.execute(
            f"""
               SELECT value, timestamp
               FROM status_entries
               WHERE faction_code = %s
               ORDER BY timestamp DESC
               LIMIT {int(avg_entries)}
            """,
            (faction_id,),
        )
        entries = cursor.fetchall()
        latest = entries[0] if entries else None
        previous = entries[1] if len(entries) > 1 else None

        cursor.execute(
            "SELECT COUNT(*) FROM status_entries WHERE faction_code = %s",
            (faction_id,),
        )
        entry_count = cursor.fetchone()[0]

        return entries, entry_count, latest, previous

    @staticmethod
    def _compute_faction_status(conn, entries, latest, previous, name, reputation_table_name):
        """Compute rate, rep level, and goal data for a faction. Returns (status, rep_level, value_delta)."""
        status = {
            "time_delta": 0,
            "value_delta": 0,
            "raw_value_delta_per_minute": 0.0,
            "avg_value_delta_per_minute": 0.0,
            "minutes_to_goal": 0.0,
            "reputation_level": "Unknown",
        }
        rep_level = "Unknown"
        value_delta = 0

        if not (latest and previous):
            return status, rep_level, value_delta

        rep_dao = reputations_dao.ReputationsDAO.get_dao_by_faction_name(name)
        if rep_dao is None:
            rep_dao = reputations_dao.ReputationsDAO(conn, reputation_table_name)
        reputation_row = rep_dao.find_reputation_by_value(conn, latest[0])

        t1 = datetime.fromisoformat(previous[1])
        t2 = datetime.fromisoformat(latest[1])
        time_diff_mins = (t2 - t1).total_seconds() / 60
        value_delta = latest[0] - previous[0]
        rep_level = reputation_row[0] if reputation_row else "Unknown"

        if time_diff_mins <= 0:
            return status, rep_level, value_delta

        raw_rate = value_delta / time_diff_mins
        oldest = entries[-1]
        avg_span_mins = (t2 - datetime.fromisoformat(oldest[1])).total_seconds() / 60
        avg_rate = (latest[0] - oldest[0]) / avg_span_mins if avg_span_mins > 0 else raw_rate

        status.update({
            "time_delta": time_diff_mins,
            "value_delta": value_delta,
            "raw_value_delta_per_minute": raw_rate,
            "avg_value_delta_per_minute": avg_rate,
        })

        if reputation_row is not None:
            status["reputation_level"] = reputation_row[0]
            status["next_rep_level"] = rep_dao.find_next_reputation_name(conn, reputation_row[2])
            status["goal_value"] = rep_dao.find_next_reputation_low_limit(conn, reputation_row[2])
            if avg_rate > 0 and reputation_row[2] is not None:
                dist = reputation_row[2] - latest[0]
                goal_mins = round(dist / avg_rate, 2)
                status["minutes_to_goal"] = goal_mins
                status["minutes"] = goal_mins
        else:
            status["minutes_to_goal"] = 0.0
            status["minutes"] = 0.0

        return status, rep_level, value_delta

    @staticmethod
    def _sort_faction_summary(result, sort_by):
        """Sort faction summary list in-place by key. Prefix with '-' for descending."""
        if not sort_by:
            return result

        reverse = sort_by.startswith("-")
        key = sort_by.lstrip("-")

        sort_keys = {
            "name":           lambda x: x["name"].lower(),
            "display_order":  lambda x: x["display_order"] if x["display_order"] is not None else 999999,
            "current_value":  lambda x: x["current_value"],
            "last_delta":     lambda x: x["last_delta"],
            "remaining_time": lambda x: x["status"].get("minutes", 0),
            "change_rate":    lambda x: x["status"]["raw_value_delta_per_minute"],
            "rep_level":      lambda x: x["rep_level"].lower(),
            "last_updated":   lambda x: x["last_updated"] or "",
            "entry_count":    lambda x: x["entry_count"],
        }
        if key in sort_keys:
            result.sort(key=sort_keys[key], reverse=reverse)
        return result

    def get_faction_summary(self, sort_by: str | None = None) -> list[dict[str, Any]]:
        """Get summary data for all factions including latest value, delta, rates, and rep level."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           SELECT f.code, f.name, f.on_chart, f.color, f.reputation_table_name, f.display_order, f.reputation_dao_name
                           FROM factions f
                           ORDER BY f.display_order
                           """)
            factions_list = cursor.fetchall()

            result = []
            for faction_code, name, on_chart, color, reputation_table_name, display_order, reputation_dao_name in factions_list:
                entries, entry_count, latest, previous = self._fetch_entries_and_count(cursor, faction_code)
                status, rep_level, value_delta = self._compute_faction_status(
                    conn, entries, latest, previous, name, reputation_table_name
                )
                result.append({
                    "id": faction_code,   # backward-compat alias
                    "code": faction_code,
                    "name": name,
                    "faction_type": faction_code,
                    "on_chart": on_chart,
                    "display_order": display_order,
                    "reputation_table_name": reputation_table_name,
                    "reputation_dao_name": reputation_dao_name,
                    "color": color,
                    "current_value": latest[0] if latest else 0,
                    "rep_level": rep_level,
                    "last_delta": value_delta,
                    "last_updated": latest[1] if latest else None,
                    "entry_count": entry_count,
                    "status": status,
                })

        return self._sort_faction_summary(result, sort_by)
