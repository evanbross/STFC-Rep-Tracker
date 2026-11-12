# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-12
"""A small blocking pool of reusable Postgres connections (N-P1).

Each new connection to Neon costs a TCP + TLS handshake, which takes far
longer than a typical query here. The pool keeps every connection it opens,
up to `max_size`, and lends them out again.

Why not psycopg2's ThreadedConnectionPool:

- It raises PoolError once every connection is lent out. A semaphore here
  makes the extra caller wait for a free connection instead.
- It keeps only `minconn` connections idle and closes the rest when they are
  returned, so every burst of Dashboard requests re-opened connections.

Neon suspends idle computes and drops their connections. A connection that
has been idle longer than `idle_check_seconds` is checked with `SELECT 1`
before it is lent out, and replaced if the check fails. Busy connections
skip the check, so a burst of requests costs no extra round trips.

Connections are opened on first use, never at construction, so every idle
connection has a known idle time. Idle connections are reused last-in,
first-out: the most recently used one is the most likely to still be alive.

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
from psycopg2.pool import PoolError

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
        self._dsn = dsn
        # Bounds leased connections. A connection is only opened when no idle
        # one is left, so the open total never exceeds max_size either.
        self._slots = threading.BoundedSemaphore(max_size)
        self._idle_check_seconds = idle_check_seconds
        # (connection, monotonic time it was returned), newest last.
        self._idle: list[tuple[PgConnection, float]] = []
        self._idle_lock = threading.Lock()
        self._closed = False

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
        """Close every idle connection; leased ones are closed when returned.

        The pool cannot be used afterwards.
        """
        with self._idle_lock:
            self._closed = True
            idle, self._idle = self._idle, []
        for conn, _ in idle:
            conn.close()

    def _checkout(self) -> PgConnection:
        while True:
            with self._idle_lock:
                if self._closed:
                    raise PoolError("connection pool is closed")
                if not self._idle:
                    break
                conn, returned_at = self._idle.pop()
            if time.monotonic() - returned_at < self._idle_check_seconds or self._is_alive(conn):
                return conn
            logger.info("Pooled DB connection was dropped while idle; discarding it")
            conn.close()
        return psycopg2.connect(self._dsn)

    def _checkin(self, conn: PgConnection) -> None:
        broken = bool(conn.closed) or conn.get_transaction_status() != psycopg2.extensions.TRANSACTION_STATUS_IDLE
        with self._idle_lock:
            if not broken and not self._closed:
                self._idle.append((conn, time.monotonic()))
                return
        conn.close()

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
