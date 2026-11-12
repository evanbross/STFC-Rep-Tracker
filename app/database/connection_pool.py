# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""A small blocking pool of reusable Postgres connections (N-P1).

Each new connection to Neon costs a TCP + TLS handshake, which takes far
longer than a typical query here. The pool keeps up to `max_size` connections
open and lends them out.

Two problems a plain psycopg2 pool has, and how this one handles them:

- ThreadedConnectionPool raises PoolError once every connection is lent out.
  A semaphore makes the extra caller wait for a free connection instead.
- Neon suspends idle computes and drops their connections. A connection that
  has been idle longer than `idle_check_seconds` is checked with `SELECT 1`
  before it is lent out, and replaced if the check fails. Busy connections
  skip the check, so a burst of Dashboard requests costs no extra round trips.

The pool holds no session state: `Database.connect()` always ends the
transaction before a connection comes back, so any caller can take any connection.
"""
import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)

DEFAULT_MAX_SIZE = 8
DEFAULT_IDLE_CHECK_SECONDS = 30.0


class ConnectionPool:
    """Lend out pooled connections, waiting when all are in use."""

    def __init__(
        self,
        dsn: str,
        max_size: int = DEFAULT_MAX_SIZE,
        idle_check_seconds: float = DEFAULT_IDLE_CHECK_SECONDS,
    ) -> None:
        self._pool = ThreadedConnectionPool(1, max_size, dsn)
        self._slots = threading.BoundedSemaphore(max_size)
        self._idle_check_seconds = idle_check_seconds
        self._returned_at: dict[int, float] = {}
        self._returned_at_lock = threading.Lock()
        # ai: claude-opus-5-5 | 2026-11-12
        # ThreadedConnectionPool opens a connection up front. Pass it through
        # _checkin so it gets an idle timestamp too: _checkout reads "no
        # timestamp" as "just opened" and skips the liveness check, so without
        # this the first request after a long idle start-up gets a connection
        # Neon has already dropped.
        self._checkin(self._pool.getconn())

    @contextmanager
    def lease(self) -> Iterator[PgConnection]:
        """Yield a live connection and take it back afterwards.

        The caller must end its transaction (commit or rollback) before the
        block exits. A connection that is closed or broken is discarded
        instead of being reused.
        """
        with self._slots:
            conn = self._checkout()
            try:
                yield conn
            finally:
                self._checkin(conn)

    def close(self) -> None:
        """Close every connection; the pool cannot be used afterwards."""
        self._pool.closeall()

    def _checkout(self) -> PgConnection:
        conn = self._pool.getconn()
        with self._returned_at_lock:
            returned_at = self._returned_at.pop(id(conn), None)
        if returned_at is None or time.monotonic() - returned_at < self._idle_check_seconds:
            return conn
        if self._is_alive(conn):
            return conn
        logger.info("Pooled DB connection was dropped while idle; opening a new one")
        self._pool.putconn(conn, close=True)
        return self._pool.getconn()

    def _checkin(self, conn: PgConnection) -> None:
        broken = bool(conn.closed) or conn.get_transaction_status() != psycopg2.extensions.TRANSACTION_STATUS_IDLE
        if not broken:
            with self._returned_at_lock:
                self._returned_at[id(conn)] = time.monotonic()
        self._pool.putconn(conn, close=broken)

    @staticmethod
    def _is_alive(conn: PgConnection) -> bool:
        if conn.closed:
            return False
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            conn.rollback()
            return True
        except psycopg2.Error:
            return False
