# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import importlib
import logging
import re
import threading
from typing import Any

from app.database import reputation_tiers
from app.domain_errors import NotFoundError, NoUpdatableFieldsError

logger = logging.getLogger(__name__)
TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ReputationsDAO:
    dao_instances_by_faction: dict[str, "ReputationsDAO"] = {}
    dao_instances_by_table_name: dict[str, "ReputationsDAO"] = {}
    dao_instances_by_class: dict[str, "ReputationsDAO"] = {}
    _registry_lock = threading.Lock()

    def __init__(self, db: Any, table_name: str) -> None:
        self.db = db
        self.table_name = self._validate_table_name(table_name)
        # ai: claude-opus-5-5 | 2026-11-06
        # Tier rows are seed data that change only through update_row, so
        # they are read once and served from memory (N-P2, N-P6).
        self._rows: list[dict[str, Any]] | None = None
        self._tiers_lock = threading.Lock()

    @staticmethod
    def get_dao_by_faction_name(name: str) -> "ReputationsDAO | None":
        with ReputationsDAO._registry_lock:
            return ReputationsDAO.dao_instances_by_faction.get(name)

    @staticmethod
    def get_dao_by_table_name(table_name: str) -> "ReputationsDAO | None":
        with ReputationsDAO._registry_lock:
            return ReputationsDAO.dao_instances_by_table_name.get(table_name)

    @staticmethod
    def get_dao_by_class_name(name: str) -> "ReputationsDAO | None":
        with ReputationsDAO._registry_lock:
            return ReputationsDAO.dao_instances_by_class.get(name)

    @staticmethod
    def get_all_dao_by_class_name() -> dict[str, "ReputationsDAO"]:
        with ReputationsDAO._registry_lock:
            return dict(ReputationsDAO.dao_instances_by_class)

    @classmethod
    def get_known_table_names(cls) -> set[str]:
        with cls._registry_lock:
            return {dao.table_name for dao in cls.dao_instances_by_faction.values()}

    # ai: claude-opus-5-5 | 2026-11-06
    @staticmethod
    def _get_columns(cursor: Any, table_name: str) -> dict[str, str]:
        """Map lowercase column name -> actual column name for table_name in the active schema."""
        ReputationsDAO._validate_table_name(table_name)
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s AND table_schema = current_schema()",
            (table_name,),
        )
        return {row[0].lower(): row[0] for row in cursor.fetchall()}

    @staticmethod
    def _validate_table_name(table_name: str) -> str:
        if not TABLE_NAME_PATTERN.fullmatch(table_name):
            raise ValueError(f"Invalid reputation table name: {table_name}")
        return table_name

    @staticmethod
    def register_dao(faction_name: str, dao: "ReputationsDAO") -> None:
        with ReputationsDAO._registry_lock:
            ReputationsDAO.dao_instances_by_faction[faction_name] = dao
            ReputationsDAO.dao_instances_by_table_name[dao.table_name] = dao
            ReputationsDAO.dao_instances_by_class[dao.__class__.__name__] = dao

    @staticmethod
    def initialize_dao_instances(db: Any, factions_dao: Any, cursor: Any | None = None) -> None:
        """Initialize all reputation DAO instances based on factions in the database"""
        # Clear existing instances to avoid duplicates if re-initialized
        with ReputationsDAO._registry_lock:
            ReputationsDAO.dao_instances_by_faction.clear()
            ReputationsDAO.dao_instances_by_table_name.clear()
            ReputationsDAO.dao_instances_by_class.clear()

        if cursor is None:
            factions = factions_dao.get_all_factions()
        else:
            factions = factions_dao.get_all_factions_with_cursor(cursor)
        for faction in factions:
            rep_table_name = faction.get("reputation_table_name")
            rep_dao_name = faction.get("reputation_dao_name")
            faction_name = faction.get("name")

            if not rep_dao_name:
                continue
            if not rep_table_name:
                logger.error("Faction %s has no reputation table name", faction_name)
                continue

            # If we haven't created a DAO for this table yet, do it now
            rep_dao = ReputationsDAO.get_dao_by_class_name(rep_dao_name)
            if rep_dao is None:
                try:
                    ReputationsDAO._validate_table_name(rep_table_name)
                    module = importlib.import_module(
                        "app.database." + rep_table_name + "_dao"
                    )
                    dao_class = getattr(module, rep_dao_name)
                    # Instantiate the DAO. Most specialized DAOs take (db)
                    # while the base ReputationsDAO takes (db, table_name)
                    if dao_class == ReputationsDAO:
                        rep_dao = dao_class(db, rep_table_name)
                    else:
                        rep_dao = dao_class(db)
                except (ImportError, AttributeError, ValueError) as e:
                    logger.error(
                        f"Failed to initialize DAO {rep_dao_name} for faction {faction_name}: {e}"
                    )
                    continue

            # Register the DAO for this specific faction name
            ReputationsDAO.register_dao(faction_name, rep_dao)

        logger.info(
            f"Initialized {len(ReputationsDAO.dao_instances_by_faction)} reputation DAO mappings"
        )

    # ai: claude-opus-5-5 | 2026-11-06
    def get_all(self) -> list[dict[str, Any]]:
        """Return every tier row, ordered by low_limit, from the in-memory cache."""
        return [dict(row) for row in self._cached_rows()]

    # ai: claude-opus-5-5 | 2026-11-06
    def load_tiers(self, cursor: Any) -> None:
        """Fill the tier cache using the caller's cursor (init_database does this after seeding)."""
        rows = self._read_rows(cursor)
        with self._tiers_lock:
            self._rows = rows

    # ai: claude-opus-5-5 | 2026-11-06
    def invalidate_tiers(self) -> None:
        """Drop the cache; the next read reloads it from the table."""
        with self._tiers_lock:
            self._rows = None

    # ai: claude-opus-5-5 | 2026-11-06
    def find_tier(self, value: int) -> dict[str, Any] | None:
        """Return the tier whose range contains value, or None."""
        row = reputation_tiers.find_tier(self._cached_rows(), value)
        return dict(row) if row else None

    # ai: claude-opus-5-5 | 2026-11-06
    def find_next_tier(self, current_high_limit: int | None) -> dict[str, Any] | None:
        """Return the tier that follows a tier ending at current_high_limit, or None."""
        row = reputation_tiers.find_next_tier(self._cached_rows(), current_high_limit)
        return dict(row) if row else None

    # ai: claude-opus-5-5 | 2026-11-06
    def update_row(self, row_id: int, fields: dict[str, Any]) -> None:
        """Set the given columns on one tier row, then refresh the cache.

        Only fields that are real columns of this table are written; column
        names come from information_schema, never from the caller.
        Raises NoUpdatableFieldsError when no field matches a column, NotFoundError when
        the table or row does not exist.
        """
        with self.db.connect() as conn, conn.cursor() as cursor:
            columns = self._get_columns(cursor, self.table_name)
            if not columns:
                raise NotFoundError(f"Table '{self.table_name}' not found")
            updates = {columns[field]: value for field, value in fields.items() if field in columns}
            if not updates:
                raise NoUpdatableFieldsError("No valid fields to update")
            assignments = ", ".join(f'"{column}" = %s' for column in updates)
            cursor.execute(
                f'UPDATE "{self.table_name}" SET {assignments} WHERE id = %s', [*updates.values(), row_id]
            )
            if cursor.rowcount == 0:
                raise NotFoundError(f"Row {row_id} not found in '{self.table_name}'")
        # Invalidate only after the commit, so no reader can cache the old row again.
        self.invalidate_tiers()

    def _cached_rows(self) -> list[dict[str, Any]]:
        with self._tiers_lock:
            if self._rows is None:
                with self.db.connect() as conn, conn.cursor() as cursor:
                    self._rows = self._read_rows(cursor)
            return self._rows

    def _read_rows(self, cursor: Any) -> list[dict[str, Any]]:
        """Read every tier row, choosing the SELECT from the columns this table has."""
        columns = self._get_columns(cursor, self.table_name)
        table = self.table_name
        if "high_limit" in columns:
            cursor.execute(f'SELECT id, name, low_limit, high_limit FROM "{table}" ORDER BY low_limit')
            return [
                {"id": r[0], "name": r[1], "low_limit": r[2], "high_limit": r[3]}
                for r in cursor.fetchall()
            ]
        if "messages_count" in columns and "credit_amount" in columns:
            cursor.execute(
                f'SELECT id, name, low_limit, messages_count, credit_amount FROM "{table}" ORDER BY low_limit'
            )
            return [
                {"id": r[0], "name": r[1], "low_limit": r[2], "messages_count": r[3], "credit_amount": r[4]}
                for r in cursor.fetchall()
            ]
        cursor.execute(f'SELECT id, name, low_limit FROM "{table}" ORDER BY low_limit')
        return [
            {"id": r[0], "name": r[1], "low_limit": r[2], "high_limit": None}
            for r in cursor.fetchall()
        ]

    def create_table(self, cursor: Any) -> None:
        """Create the current reputation table schema."""
        cursor.execute(f"""
                       CREATE TABLE IF NOT EXISTS "{self.table_name}"
                       (
                           id         SERIAL PRIMARY KEY,
                           name       TEXT NOT NULL,
                           low_limit  BIGINT NOT NULL,  -- ai: claude-opus-5-5 | 2026-11-06 (matches live schema)
                           high_limit BIGINT  -- ai: claude-opus-5-5 | 2026-11-06 (matches live schema)
                       )
                """)

        cursor.execute(
            f'CREATE UNIQUE INDEX IF NOT EXISTS "{self.table_name}_name_key" '
            f'ON "{self.table_name}" (name)'
        )

        # Apply initial reputations
        self.apply_initial_reputations(cursor)

    def get_initial_reputations(self) -> list[tuple]:
        raise NotImplementedError("subclasses must define initial reputation rows")

    def apply_initial_reputations(self, cursor: Any) -> None:
        columns = self._get_columns(cursor, self.table_name)

        # Check if high_limit exists (some special tables like DTI might not have it yet or at all)
        has_high_limit = "high_limit" in columns

        for entry in self.get_initial_reputations():
            if has_high_limit and len(entry) >= 3:
                name, low_limit, high_limit = entry[0], entry[1], entry[2]
                cursor.execute(
                    f"""
                               INSERT INTO "{self.table_name}" (name, low_limit, high_limit)
                               VALUES (%s, %s, %s)
                               ON CONFLICT (name) DO UPDATE
                                   SET low_limit  = EXCLUDED.low_limit,
                                       high_limit = EXCLUDED.high_limit
                               """,
                    (name, low_limit, high_limit),
                )
            else:
                # Handle cases with fewer columns or missing high_limit
                name, low_limit = entry[0], entry[1]
                cursor.execute(
                    f"""
                               INSERT INTO "{self.table_name}" (name, low_limit)
                               VALUES (%s, %s)
                               ON CONFLICT (name) DO UPDATE
                                   SET low_limit = EXCLUDED.low_limit
                               """,
                    (name, low_limit),
                )

    def get_table_name(self) -> str:
        return self.table_name
