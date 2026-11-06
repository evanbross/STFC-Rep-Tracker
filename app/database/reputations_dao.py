# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import functools
import hashlib
import importlib
import json
import logging
import pkgutil
import re
import threading
from typing import Any

import app.database as database_package
from app.database import reputation_tiers
from app.domain_errors import NotFoundError, NoUpdatableFieldsError

logger = logging.getLogger(__name__)
TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MODULE_SUFFIX = "_reputations_dao"


class ReputationsDAO:
    # ai: claude-opus-5-5 | 2026-11-06
    # One instance per *_reputations_dao.py implementation, keyed by table name
    # (R5). The registry no longer depends on faction rows, so a faction created
    # or edited at runtime resolves its DAO without a restart.
    _instances_by_table: dict[str, "ReputationsDAO"] = {}
    _registry_lock = threading.Lock()

    def __init__(self, db: Any, table_name: str) -> None:
        self.db = db
        self.table_name = self._validate_table_name(table_name)
        # ai: claude-opus-5-5 | 2026-11-06
        # Tier rows are seed data that change only through update_row, so
        # they are read once and served from memory (N-P2, N-P6).
        self._rows: list[dict[str, Any]] | None = None
        self._tiers_lock = threading.Lock()

    # ai: claude-opus-5-5 | 2026-11-06
    @staticmethod
    @functools.cache
    def available_implementations() -> dict[str, type["ReputationsDAO"]]:
        """Map table name -> DAO class for every app/database/<table>_dao.py module.

        The Python files are the source of truth for which reputation types
        exist, and a faction may only reference one of these tables. Each module
        must define exactly one ReputationsDAO subclass, for the table its file
        is named after (fkr_reputations_dao.py -> fkr_reputations).
        """
        implementations: dict[str, type[ReputationsDAO]] = {}
        for module_info in pkgutil.iter_modules(database_package.__path__):
            if not module_info.name.endswith(_MODULE_SUFFIX):
                continue
            module = importlib.import_module(f"{database_package.__name__}.{module_info.name}")
            classes = [
                obj for obj in vars(module).values()
                if isinstance(obj, type) and issubclass(obj, ReputationsDAO)
                and obj is not ReputationsDAO and obj.__module__ == module.__name__
            ]
            if len(classes) != 1:
                raise TypeError(
                    f"{module.__name__} must define exactly one ReputationsDAO subclass, found {len(classes)}"
                )
            implementations[module_info.name.removesuffix("_dao")] = classes[0]
        return dict(sorted(implementations.items()))

    # ai: claude-opus-5-5 | 2026-11-06
    @classmethod
    def available_types(cls) -> list[dict[str, str]]:
        """[{table_name, dao_name}] for the Factions form and request validation."""
        return [
            {"table_name": table, "dao_name": dao_class.__name__}
            for table, dao_class in cls.available_implementations().items()
        ]

    # ai: claude-opus-5-5 | 2026-11-06
    @classmethod
    def initialize_dao_instances(cls, db: Any) -> None:
        """Create one DAO per available implementation. No database access."""
        instances: dict[str, ReputationsDAO] = {}
        for table, dao_class in cls.available_implementations().items():
            dao = dao_class(db)
            if dao.table_name != table:
                raise TypeError(
                    f"{dao_class.__name__} uses table {dao.table_name!r}, but its module is named for {table!r}"
                )
            instances[table] = dao
        with cls._registry_lock:
            cls._instances_by_table = instances
        logger.info("Initialized %d reputation DAOs", len(instances))

    @classmethod
    def get_dao_by_table_name(cls, table_name: str) -> "ReputationsDAO | None":
        with cls._registry_lock:
            return cls._instances_by_table.get(table_name)

    # ai: claude-opus-5-5 | 2026-11-06
    @classmethod
    def all_daos(cls) -> dict[str, "ReputationsDAO"]:
        """Every registered DAO, keyed by table name."""
        with cls._registry_lock:
            return dict(cls._instances_by_table)

    @classmethod
    def get_known_table_names(cls) -> set[str]:
        with cls._registry_lock:
            return set(cls._instances_by_table)

    # ai: claude-opus-5-5 | 2026-11-06
    def seed_fingerprint(self) -> str:
        """Hash of this implementation's seed rows. A change triggers a reseed at startup."""
        payload = json.dumps([type(self).__name__, [list(row) for row in self.get_initial_reputations()]])
        return hashlib.sha256(payload.encode()).hexdigest()

    # ai: claude-opus-5-5 | 2026-11-06
    @classmethod
    def sync_seed_data(cls, cursor: Any) -> list[str]:
        """Create and seed each tier table whose seed rows changed since it was last seeded.

        Returns the tables seeded. Tier rows edited through the UI therefore
        survive restarts until the seed in code changes. Needs the
        reputation_seed table (migration v1) and runs in the caller's transaction.
        """
        cursor.execute("SELECT table_name, fingerprint FROM reputation_seed")
        stored = dict(cursor.fetchall())
        seeded = []
        for table, dao in cls.all_daos().items():
            fingerprint = dao.seed_fingerprint()
            if stored.get(table) == fingerprint:
                continue
            dao.create_table(cursor)
            cursor.execute(
                """
                INSERT INTO reputation_seed (table_name, fingerprint) VALUES (%s, %s)
                ON CONFLICT (table_name) DO UPDATE SET fingerprint = EXCLUDED.fingerprint, seeded_at = NOW()
                """,
                (table, fingerprint),
            )
            dao.invalidate_tiers()
            seeded.append(table)
        return seeded

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

    # ai: claude-opus-5-5 | 2026-11-06
    def get_all(self) -> list[dict[str, Any]]:
        """Return every tier row, ordered by low_limit, from the in-memory cache."""
        return [dict(row) for row in self._cached_rows()]

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
