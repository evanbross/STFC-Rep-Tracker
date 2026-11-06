# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""ConnectionPool and Database.connect() against the real test database (N-P1)."""
import threading
import time
from collections.abc import Iterator

import psycopg2
import pytest

from app.database.connection_pool import ConnectionPool
from app.database.database import Database

pytestmark = pytest.mark.db


def _backend_pid(conn: psycopg2.extensions.connection) -> int:
    with conn.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        pid = cursor.fetchone()[0]
    conn.rollback()
    return pid


@pytest.fixture(name="pool")
def fixture_pool(db: Database) -> Iterator[ConnectionPool]:
    """A separate small pool on the test database, so tests can tune its limits."""
    test_pool = ConnectionPool(db.db_url, max_size=2, idle_check_seconds=0)
    yield test_pool
    test_pool.close()


def test_connections_are_reused(db: Database) -> None:
    with db.connect() as conn:
        first = _backend_pid(conn)
    with db.connect() as conn:
        second = _backend_pid(conn)

    assert first == second


def test_connection_dropped_while_idle_is_replaced(pool: ConnectionPool, db: Database) -> None:
    """Neon drops connections when it suspends; the next lease must not fail."""
    with pool.lease() as conn:
        dropped = _backend_pid(conn)
    with db.connect() as admin, admin.cursor() as cursor:
        cursor.execute("SELECT pg_terminate_backend(%s)", (dropped,))

    with pool.lease() as conn:
        assert _backend_pid(conn) != dropped


def test_failed_block_rolls_back_and_pool_recovers(db: Database) -> None:
    with pytest.raises(psycopg2.errors.UndefinedTable):
        with db.connect() as conn, conn.cursor() as cursor:
            cursor.execute("INSERT INTO factions (code, name) VALUES ('ZZZ', 'Rolled back')")
            cursor.execute("SELECT * FROM no_such_table")

    with db.connect() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM factions WHERE code = 'ZZZ'")
        assert cursor.fetchone()[0] == 0


def test_open_transaction_is_not_handed_to_the_next_caller(pool: ConnectionPool) -> None:
    """A lease that exits mid-transaction is discarded, not reused with its state."""
    with pool.lease() as conn:
        leaked = _backend_pid(conn)
        conn.cursor().execute("SELECT 1")    # opens a transaction and leaves it open

    with pool.lease() as conn:
        assert _backend_pid(conn) != leaked


def test_extra_callers_wait_instead_of_failing(pool: ConnectionPool) -> None:
    """ThreadedConnectionPool alone raises PoolError past max_size; this pool queues."""
    errors: list[BaseException] = []

    def hold() -> None:
        try:
            with pool.lease() as conn:
                _backend_pid(conn)
                time.sleep(0.3)
        except BaseException as exc:  # collected and asserted on the main thread
            errors.append(exc)

    threads = [threading.Thread(target=hold) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
