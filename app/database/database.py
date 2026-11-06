# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging
from collections.abc import Iterator
from contextlib import closing, contextmanager

import psycopg2
from psycopg2.extensions import connection as PgConnection

from app.database import factions_dao, migrations, status_entries_dao
from app.database.connection_pool import ConnectionPool
from app.database.faction_selected_snippets_dao import FactionSelectedSnippetsDAO
from app.database.reputations_dao import ReputationsDAO
from app.database.target_types_dao import TargetTypesDAO
from app.database.territory_systems_dao import TerritorySystemsDAO

logger = logging.getLogger(__name__)

# Stable advisory lock key used to serialize init_database across workers.
# Multiple Gunicorn workers can race to run init at startup; the advisory lock
# makes them queue so only one performs DDL/upserts at a time.
_INIT_ADVISORY_LOCK_ID = 0x535446435F5245


class Database:

    # ai: claude-opus-5-5 | 2026-11-06
    def __init__(self, db_url: str, direct_url: str | None = None) -> None:
        """db_url serves app queries through the pool. direct_url (Neon's
        non-PgBouncer endpoint) is used only for init_database's session-level
        advisory lock, which a transaction-pooling proxy cannot hold."""
        self.db_url = db_url
        self.direct_url = direct_url or db_url
        self._pool = ConnectionPool(db_url)
        self.factions_dao = factions_dao.FactionsDAO(self)
        self.factions = self.factions_dao

        self.status_entries_dao = status_entries_dao.StatusEntriesDAO(self)
        self.status_entries = self.status_entries_dao

        self.selected_snippets_dao = FactionSelectedSnippetsDAO(self)
        self.selected_snippets = self.selected_snippets_dao

        self.territory_systems_dao = TerritorySystemsDAO(self)
        self.territory_systems = self.territory_systems_dao

        self.target_types_dao = TargetTypesDAO(self)
        self.target_types = self.target_types_dao

        self.init_database()

    # ai: claude-opus-5-5 | 2026-11-06
    @contextmanager
    def connect(self) -> Iterator[PgConnection]:
        """Yield a pooled connection; commit on success, roll back on error, then return it to the pool."""
        with self._pool.lease() as conn:
            try:
                yield conn
                conn.commit()
            except BaseException:
                # A dead connection can fail the rollback too; the pool then
                # sees a non-idle connection and discards it.
                try:
                    conn.rollback()
                except psycopg2.Error:
                    logger.warning("Rollback failed; the connection will be discarded", exc_info=True)
                raise

    def close(self) -> None:
        """Close all pooled connections."""
        self._pool.close()

    # ai: claude-opus-5-5 | 2026-11-06
    def init_database(self) -> None:
        """Bring the schema to head, register reputation DAOs, and seed changed tier tables.

        Runs in one transaction under a session-level advisory lock, so Gunicorn
        workers starting together queue instead of racing, and a failed
        migration leaves the database untouched. At head this costs the lock
        and two small SELECTs; tier rows load lazily on first use.
        """
        ReputationsDAO.initialize_dao_instances(self)
        # Closing the session releases the advisory lock, even if unlocking would fail.
        with closing(psycopg2.connect(self.direct_url)) as conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_lock(%s)", (_INIT_ADVISORY_LOCK_ID,))
                    applied = migrations.migrate(cursor)
                    seeded = ReputationsDAO.sync_seed_data(cursor)
                conn.commit()
            except psycopg2.Error:
                conn.rollback()
                logger.exception("Database initialization failed; no changes were applied")
                raise
        if applied or seeded:
            logger.info("Schema migrations applied: %s; tier tables seeded: %s", applied or "none", seeded or "none")
        else:
            logger.info("Database schema is at version %d; nothing to do", migrations.HEAD_VERSION)
