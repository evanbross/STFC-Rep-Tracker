# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Ordered schema migrations, recorded in schema_version (R7).

Database.init_database runs migrate() under its advisory lock, in one
transaction: either every pending migration applies or none does. A database
already at head costs one SELECT instead of re-running every CREATE.

Rules for adding a migration:
- Append a new Migration with the next version number. Never edit or reorder
  one that has shipped: a database records only the version it reached, so
  changing old SQL changes nothing for it, and the schemas drift apart.
- Write SQL literals here instead of calling DAO code, so a DAO edit can't
  quietly change what an old version means.
- A migration must also be safe to run on a database created by the
  pre-migration code (pre-R7, every table was CREATE TABLE IF NOT EXISTS).

Reputation tier tables are not managed here: there is one per
*_reputations_dao.py file, and ReputationsDAO.sync_seed_data creates and
seeds them.
"""
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    apply: Callable[[Any], None]


def _sql(*statements: str) -> Callable[[Any], None]:
    def apply(cursor: Any) -> None:
        for statement in statements:
            cursor.execute(statement)
    return apply


# v1: the schema the pre-migration code created on an empty database, frozen
# as of 2026-11-06. On an existing database every statement is a no-op apart
# from the one-time snippet_unselected backfill, which used to run on every start.
_V1_BASELINE = _sql(
    """
    CREATE TABLE IF NOT EXISTS factions (
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
    """,
    """
    UPDATE factions
    SET snippet_unselected = 'RepButton' || upper(substr(code, 1, 1)) || lower(substr(code, 2)) || '.jpg'
    WHERE snippet_unselected IS NULL AND code IS NOT NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS status_entries (
        id           SERIAL PRIMARY KEY,
        faction_code TEXT NOT NULL,
        timestamp    TEXT NOT NULL,
        value        BIGINT NOT NULL,
        value_delta  INTEGER DEFAULT 0,
        FOREIGN KEY (faction_code) REFERENCES factions(code) ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS faction_selected_snippets (
        id           SERIAL PRIMARY KEY,
        faction_id   TEXT NOT NULL,
        filename     TEXT NOT NULL,
        snippet_type TEXT,
        FOREIGN KEY (faction_id) REFERENCES factions(code) ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS territory_systems (
        id          SERIAL PRIMARY KEY,
        name        VARCHAR(100) UNIQUE NOT NULL,
        day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
        event_time  TIME NOT NULL
    )
    """,
    # The preference list is frozen here on purpose. If TargetPreference changes,
    # add a migration that replaces this CHECK; test_migrations compares the two.
    """
    CREATE TABLE IF NOT EXISTS target_types (
        id                    SERIAL PRIMARY KEY,
        system_name           TEXT NOT NULL,
        template_filename     TEXT NOT NULL,
        display_name          TEXT,
        preference            TEXT NOT NULL DEFAULT 'unknown'
                                  CHECK (preference IN ('unknown', 'target', 'avoid')),
        sample_image_filename TEXT,
        example_name          TEXT,
        example_level         INTEGER,
        times_seen            INTEGER NOT NULL DEFAULT 1,
        first_seen_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_seen_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (system_name, template_filename)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reputation_seed (
        table_name  TEXT PRIMARY KEY,
        fingerprint TEXT NOT NULL,
        seeded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
)


def _replace_foreign_keys(table: str, column: str, constraint: str) -> str:
    """SQL that drops every FK on `table` and re-adds one ON UPDATE CASCADE FK to factions(code).

    Pre-R7 databases named these constraints differently (and one was NOT VALID),
    so they are looked up by table rather than by name.
    """
    return f"""
    DO $$
    DECLARE fk record;
    BEGIN
        FOR fk IN SELECT conname FROM pg_constraint
                  WHERE conrelid = '{table}'::regclass AND contype = 'f'
        LOOP
            EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', fk.conname);
        END LOOP;
        ALTER TABLE {table} ADD CONSTRAINT {constraint}
            FOREIGN KEY ({column}) REFERENCES factions(code) ON UPDATE CASCADE;
    END $$
    """


# v2: bring databases created by older code into line with v1. Found by
# diffing a Neon copy of production against a fresh v1 schema.
_V2_RECONCILE = _sql(
    # Renaming a faction code must cascade; production's FKs did not.
    _replace_foreign_keys("status_entries", "faction_code", "status_entries_faction_code_fkey"),
    _replace_foreign_keys("faction_selected_snippets", "faction_id", "faction_selected_snippets_faction_id_fkey"),
    # FactionsDAO maps a duplicate name to 409, which needs this index.
    "CREATE UNIQUE INDEX IF NOT EXISTS factions_name_key ON factions (name)",
    # Production had NOT NULL DEFAULT '"FKRReputationsDAO"' (quotes included),
    # which broke factions without a reputation type.
    "ALTER TABLE factions ALTER COLUMN reputation_dao_name DROP NOT NULL",
    "ALTER TABLE factions ALTER COLUMN reputation_dao_name DROP DEFAULT",
    "ALTER TABLE status_entries ALTER COLUMN faction_code TYPE TEXT",
    # Never populated (N-S5); production never had it, so reads of it failed there.
    "ALTER TABLE status_entries DROP COLUMN IF EXISTS value_delta",
)

# v3 (N-S5): typed timestamps, so ordering and rate maths can't depend on
# string formatting. The app always wrote UTC; text without an offset is read as UTC.
_V3_TIMESTAMPTZ = _sql(
    "SET LOCAL TimeZone = 'UTC'",
    'ALTER TABLE status_entries ALTER COLUMN "timestamp" TYPE TIMESTAMPTZ USING "timestamp"::timestamptz',
    'CREATE INDEX IF NOT EXISTS status_entries_faction_time_idx ON status_entries (faction_code, "timestamp" DESC)',
)

# ai: claude-opus-5-5 | 2026-11-17
# v4: the Spock's Club resource each faction's reputation is exported as, so an
# export can be imported instead of captured. Unique where set: two factions
# reading one resource would be a mapping mistake. The backfill uses the game's
# resource IDs for the factions that existed when this shipped; a database
# without those codes updates nothing.
_V4_SPOCKS_RESOURCE_ID = _sql(
    "ALTER TABLE factions ADD COLUMN IF NOT EXISTS spocks_resource_id BIGINT",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS factions_spocks_resource_id_key
        ON factions (spocks_resource_id) WHERE spocks_resource_id IS NOT NULL
    """,
    """
    UPDATE factions f
    SET spocks_resource_id = known.resource_id
    FROM (VALUES
        ('FED', 970475396),   -- Federation Points
        ('KLI', 156323681),   -- Klingon Points
        ('ROM', 4135751670),  -- Romulan Points
        ('AUG', 598150761),   -- Augment Points
        ('ROG', 850817193),   -- Rogue Reputation
        ('BAJ', 1148260134),  -- Bajoran Reputation
        ('EXB', 129835460),   -- Ex-Borg Reputation
        ('S31', 1229289341),  -- Section 31 Reputation
        ('TER', 1547205906),  -- Terran Reputation
        ('DTI', 2800518458)   -- DTI Reputation
    ) AS known (code, resource_id)
    WHERE f.code = known.code AND f.spocks_resource_id IS NULL
    """,
)

# ai: claude-opus-5-5 | 2026-11-17
# v5: at most one reading per faction per instant, so an import can use ON CONFLICT
# instead of a lock to skip readings it already saved. Production had no
# duplicates when this shipped (770 rows checked). The constraint's index covers
# the same columns as v3's, which is dropped; Postgres reads it backwards for DESC.
_V5_UNIQUE_READING = _sql(
    """
    ALTER TABLE status_entries
        ADD CONSTRAINT status_entries_faction_time_key UNIQUE (faction_code, "timestamp")
    """,
    "DROP INDEX IF EXISTS status_entries_faction_time_idx",
)

MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "baseline schema", _V1_BASELINE),
    Migration(2, "reconcile pre-migration drift", _V2_RECONCILE),
    Migration(3, "status_entries.timestamp as timestamptz, indexed", _V3_TIMESTAMPTZ),
    Migration(4, "factions.spocks_resource_id for Spock's Club imports", _V4_SPOCKS_RESOURCE_ID),
    Migration(5, "one status entry per faction per instant", _V5_UNIQUE_READING),
)

HEAD_VERSION = MIGRATIONS[-1].version


def current_version(cursor: Any) -> int:
    """The highest applied version, or 0 for a database that predates schema_version."""
    cursor.execute("SELECT to_regclass('schema_version') IS NOT NULL")
    if not cursor.fetchone()[0]:
        return 0
    cursor.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
    return cursor.fetchone()[0]


def migrate(cursor: Any, migrations: Sequence[Migration] = MIGRATIONS, target: int | None = None) -> list[int]:
    """Apply pending migrations up to target (default: head) and return the versions applied.

    The caller owns the transaction and must hold the init advisory lock.
    """
    versions = [m.version for m in migrations]
    if versions != sorted(set(versions)):
        raise ValueError(f"Migration versions must be unique and ascending: {versions}")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    current = current_version(cursor)
    if current > versions[-1]:
        raise RuntimeError(
            f"Database schema is at version {current}, newer than this code knows ({versions[-1]}). "
            "Update the app before starting it against this database."
        )

    applied: list[int] = []
    for migration in migrations:
        if migration.version <= current or (target is not None and migration.version > target):
            continue
        logger.info("Applying schema migration %d: %s", migration.version, migration.description)
        migration.apply(cursor)
        cursor.execute(
            "INSERT INTO schema_version (version, description) VALUES (%s, %s)",
            (migration.version, migration.description),
        )
        applied.append(migration.version)
    return applied
