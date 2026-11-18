# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Schema migrations (R7, N-S5) and tier seeding, against real Postgres.

Covers the two starting points the Phase 4 gate names: an empty database,
and a copy of production (the Neon test branch's public schema, migrated
inside a transaction that is rolled back).
"""
import re
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime

import psycopg2
import pytest

from app.database import migrations
from app.database.database import Database
from app.database.reputations_dao import ReputationsDAO
from app.database.target_types_dao import TARGET_PREFERENCES

pytestmark = pytest.mark.db


@pytest.fixture(name="scratch_cursor")
def fixture_scratch_cursor(scratch_schema: str) -> Iterator[psycopg2.extensions.cursor]:
    with closing(psycopg2.connect(scratch_schema)) as conn, conn, conn.cursor() as cursor:
        yield cursor


def _column_type(cursor, table: str, column: str) -> str | None:
    cursor.execute(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = %s AND column_name = %s",
        (table, column),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _foreign_keys(cursor, table: str) -> list[str]:
    cursor.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = %s::regclass AND contype = 'f'",
        (table,),
    )
    return [row[0] for row in cursor.fetchall()]


def test_empty_database_reaches_head(scratch_cursor) -> None:
    applied = migrations.migrate(scratch_cursor)

    assert applied == [m.version for m in migrations.MIGRATIONS]
    assert migrations.current_version(scratch_cursor) == migrations.HEAD_VERSION
    assert _column_type(scratch_cursor, "status_entries", "timestamp") == "timestamp with time zone"
    assert _column_type(scratch_cursor, "status_entries", "value_delta") is None
    assert all("ON UPDATE CASCADE" in fk for fk in _foreign_keys(scratch_cursor, "status_entries"))


def test_database_at_head_does_nothing(scratch_cursor) -> None:
    migrations.migrate(scratch_cursor)

    assert migrations.migrate(scratch_cursor) == []


def test_newer_database_than_code_refuses_to_start(scratch_cursor) -> None:
    migrations.migrate(scratch_cursor)
    scratch_cursor.execute("INSERT INTO schema_version (version, description) VALUES (999, 'from the future')")

    with pytest.raises(RuntimeError, match="newer than this code"):
        migrations.migrate(scratch_cursor)


def test_target_preference_check_matches_the_enum(scratch_cursor) -> None:
    """v1 freezes the CHECK list; this fails when TargetPreference changes without a migration."""
    migrations.migrate(scratch_cursor)
    scratch_cursor.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = 'target_types'::regclass AND contype = 'c'"
    )
    [definition] = [row[0] for row in scratch_cursor.fetchall()]

    assert set(re.findall(r"'(\w+)'", definition)) == set(TARGET_PREFERENCES)


def test_v3_reads_every_stored_timestamp_form_as_the_same_instant(scratch_cursor) -> None:
    migrations.migrate(scratch_cursor, target=2)
    scratch_cursor.execute("INSERT INTO factions (code, name) VALUES ('FED', 'Federation')")
    for text in ("2026-01-01T13:00:00+00:00", "2026-01-01 13:00:00", "2026-01-01T15:00:00+02:00"):
        scratch_cursor.execute(
            "INSERT INTO status_entries (faction_code, timestamp, value) VALUES ('FED', %s, 1)", (text,)
        )

    # Stop at v3: these three rows are one instant, which v5's unique constraint forbids.
    migrations.migrate(scratch_cursor, target=3)  # ai: claude-opus-5-5 | 2026-11-17

    scratch_cursor.execute("SELECT DISTINCT timestamp FROM status_entries")
    assert [row[0] for row in scratch_cursor.fetchall()] == [datetime(2026, 1, 1, 13, tzinfo=UTC)]


# ai: claude-opus-5-5 | 2026-11-17
def test_v4_maps_known_factions_to_their_spocks_club_resource(scratch_cursor) -> None:
    migrations.migrate(scratch_cursor, target=3)
    scratch_cursor.execute(
        "INSERT INTO factions (code, name) VALUES ('FED', 'Federation'), ('MAV', 'Maverick')"
    )

    migrations.migrate(scratch_cursor)

    scratch_cursor.execute("SELECT code, spocks_resource_id FROM factions ORDER BY code")
    assert scratch_cursor.fetchall() == [("FED", 970475396), ("MAV", None)]
    # Unique where set, so two factions can't read the same resource; unset repeats freely.
    scratch_cursor.execute("INSERT INTO factions (code, name) VALUES ('NEW', 'New')")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        scratch_cursor.execute(
            "INSERT INTO factions (code, name, spocks_resource_id) VALUES ('DUP', 'Dup', 970475396)"
        )


# ai: claude-opus-5-5 | 2026-11-17
def test_v5_allows_one_reading_per_faction_per_instant(scratch_cursor) -> None:
    migrations.migrate(scratch_cursor)
    scratch_cursor.execute("INSERT INTO factions (code, name) VALUES ('FED', 'Federation'), ('ROM', 'Romulan')")
    insert = "INSERT INTO status_entries (faction_code, timestamp, value) VALUES (%s, '2026-01-01T13:00:00Z', 1)"
    scratch_cursor.execute(insert, ("FED",))
    scratch_cursor.execute(insert, ("ROM",))  # same instant, other faction: fine

    with pytest.raises(psycopg2.errors.UniqueViolation):
        scratch_cursor.execute(insert, ("FED",))


# ai: claude-opus-5-5 | 2026-11-18
def _v4_with_readings(cursor, *readings: tuple[str, int]) -> None:
    """A database at v4 (no uniqueness yet) holding FED readings as (timestamp, value)."""
    migrations.migrate(cursor, target=4)
    cursor.execute("INSERT INTO factions (code, name) VALUES ('FED', 'Federation')")
    for timestamp, value in readings:
        cursor.execute(
            "INSERT INTO status_entries (faction_code, timestamp, value) VALUES ('FED', %s, %s)",
            (timestamp, value),
        )


# ai: claude-opus-5-5 | 2026-11-18
def test_v5_drops_exact_duplicates_and_keeps_the_oldest_row(scratch_cursor) -> None:
    _v4_with_readings(
        scratch_cursor,
        ("2026-01-01T13:00:00Z", 100),
        ("2026-01-01T13:00:00Z", 100),
        ("2026-01-01T14:00:00Z", 200),
    )
    scratch_cursor.execute("SELECT min(id) FROM status_entries WHERE value = 100")
    oldest_id = scratch_cursor.fetchone()[0]

    migrations.migrate(scratch_cursor)

    assert migrations.current_version(scratch_cursor) == migrations.HEAD_VERSION
    scratch_cursor.execute("SELECT id, value FROM status_entries ORDER BY timestamp")
    rows = scratch_cursor.fetchall()
    assert [value for _, value in rows] == [100, 200]
    assert rows[0][0] == oldest_id


# ai: claude-opus-5-5 | 2026-11-18
def test_v5_stops_on_conflicting_duplicates_without_changing_anything(scratch_cursor) -> None:
    _v4_with_readings(scratch_cursor, ("2026-01-01T13:00:00Z", 100), ("2026-01-01T13:00:00Z", 120))

    with pytest.raises(RuntimeError, match=r"1 faction/time pairs.*FED at 2026-01-01T13:00:00\+00:00: \[100, 120\]"):
        migrations.migrate(scratch_cursor)

    assert migrations.current_version(scratch_cursor) == 4
    scratch_cursor.execute("SELECT count(*) FROM status_entries")
    assert scratch_cursor.fetchone()[0] == 2


# ai: claude-opus-5-5 | 2026-11-18
def test_v7_renames_the_snippet_faction_column_keeping_rows_and_cascade(scratch_cursor) -> None:
    migrations.migrate(scratch_cursor, target=6)
    scratch_cursor.execute("INSERT INTO factions (code, name) VALUES ('FED', 'Federation')")
    scratch_cursor.execute(
        "INSERT INTO faction_selected_snippets (faction_id, filename, snippet_type) "
        "VALUES ('FED', 'Selected-Button-Fed.jpg', 'button')"
    )

    migrations.migrate(scratch_cursor)

    assert _column_type(scratch_cursor, "faction_selected_snippets", "faction_id") is None
    scratch_cursor.execute(
        "SELECT conname FROM pg_constraint WHERE conrelid = 'faction_selected_snippets'::regclass AND contype = 'f'"
    )
    assert [row[0] for row in scratch_cursor.fetchall()] == ["faction_selected_snippets_faction_code_fkey"]
    # A code rename still reaches the snippet row through the renamed FK.
    scratch_cursor.execute("UPDATE factions SET code = 'UFP' WHERE code = 'FED'")
    scratch_cursor.execute("SELECT faction_code, filename FROM faction_selected_snippets")
    assert scratch_cursor.fetchall() == [("UFP", "Selected-Button-Fed.jpg")]


def test_failed_migration_leaves_no_trace(scratch_schema: str) -> None:
    def broken(cursor) -> None:
        cursor.execute("CREATE TABLE half_done (id INT)")
        cursor.execute("SELECT * FROM no_such_table")

    plan = (*migrations.MIGRATIONS, migrations.Migration(99, "broken", broken))
    with closing(psycopg2.connect(scratch_schema)) as conn:
        with pytest.raises(psycopg2.errors.UndefinedTable), conn.cursor() as cursor:
            migrations.migrate(cursor, plan)
        conn.rollback()
        with conn.cursor() as cursor:
            assert migrations.current_version(cursor) == 0
            cursor.execute("SELECT to_regclass('half_done')")
            assert cursor.fetchone()[0] is None


def test_production_copy_migrates_in_place(test_branch_url: str) -> None:
    """Migrate the test branch's copy of production, check it, and roll everything back."""
    with closing(psycopg2.connect(test_branch_url)) as conn, conn.cursor() as cursor:
        cursor.execute("SET LOCAL search_path TO public")
        if _column_type(cursor, "factions", "code") is None:
            pytest.skip("the test branch has no copy of production in its public schema")
        cursor.execute("SELECT count(*), min(value), max(value) FROM status_entries")
        before = cursor.fetchone()
        cursor.execute("SELECT code FROM factions LIMIT 1")
        [code] = cursor.fetchone()
        try:
            migrations.migrate(cursor)
            ReputationsDAO.sync_seed_data(cursor)

            assert migrations.current_version(cursor) == migrations.HEAD_VERSION
            cursor.execute("SELECT count(*), min(value), max(value) FROM status_entries")
            assert cursor.fetchone() == before
            assert _column_type(cursor, "status_entries", "timestamp") == "timestamp with time zone"
            for table in ("status_entries", "faction_selected_snippets"):
                assert all("ON UPDATE CASCADE" in fk for fk in _foreign_keys(cursor, table)), table
            assert _column_type(cursor, "faction_selected_snippets", "faction_code") == "text"  # ai: claude-opus-5-5 | 2026-11-18
            # A code rename now cascades; production used to reject it.
            cursor.execute("UPDATE factions SET code = 'ZZ_RENAMED' WHERE code = %s", (code,))
            cursor.execute("SELECT count(*) FROM status_entries WHERE faction_code = %s", (code,))
            assert cursor.fetchone()[0] == 0
            # A faction without a reputation type is allowed again.
            cursor.execute("INSERT INTO factions (code, name) VALUES ('ZZ_NEW', 'ZZ New')")
            with pytest.raises(psycopg2.errors.UniqueViolation):
                cursor.execute("INSERT INTO factions (code, name) VALUES ('ZZ_DUP', 'ZZ New')")
        finally:
            conn.rollback()


def test_seeding_runs_only_when_the_seed_changes(db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    fkr = ReputationsDAO.get_dao_by_table_name("fkr_reputations")
    with db.connect() as conn, conn.cursor() as cursor:
        assert ReputationsDAO.sync_seed_data(cursor) == []      # session init already seeded every table

        cursor.execute("UPDATE fkr_reputations SET high_limit = 498 WHERE name = 'Neutral'")
        assert ReputationsDAO.sync_seed_data(cursor) == []      # a UI edit survives a restart

        monkeypatch.setattr(type(fkr), "seed_fingerprint", lambda self: "changed")
        assert ReputationsDAO.sync_seed_data(cursor) == ["fkr_reputations"]
        cursor.execute("SELECT high_limit FROM fkr_reputations WHERE name = 'Neutral'")
        assert cursor.fetchone()[0] == 499                       # a changed seed wins
        conn.rollback()                                          # keep the session's seed bookkeeping intact
    fkr.invalidate_tiers()


def test_every_implementation_gets_a_tier_table(db: Database) -> None:
    """An empty database now has every tier table; before R5 it had none until a faction existed."""
    with db.connect() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT table_name FROM reputation_seed")
        seeded = {row[0] for row in cursor.fetchall()}

    assert seeded == set(ReputationsDAO.available_implementations())
