# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging
from contextlib import contextmanager

from collections.abc import Iterator

import psycopg2
from psycopg2.extensions import connection as PgConnection

from app.database import status_entries_dao, factions_dao
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

    def init_database(self):
        """Initialize the database with required tables.

        Uses a PostgreSQL session-level advisory lock to serialize this across
        all worker processes.  Without it, multiple Gunicorn workers starting
        simultaneously can deadlock on concurrent DELETEs and upserts inside
        apply_initial_reputations.
        """
        conn = psycopg2.connect(self.direct_url)  # ai: claude-opus-5-5 | 2026-11-06
        cursor = conn.cursor()
        cursor.execute("SELECT pg_advisory_lock(%s)", (_INIT_ADVISORY_LOCK_ID,))
        try:
            self._create_tables(cursor)
            ReputationsDAO.initialize_dao_instances(self, self.factions_dao, cursor)
            for dao in ReputationsDAO.get_all_dao_by_class_name().values():
                dao.create_table(cursor)
                dao.load_tiers(cursor)  # ai: claude-opus-5-5 | 2026-11-06
            conn.commit()
        except Exception as ex:
            logger.warning(f"Exception while creating table {ex.__class__.__name__}: {ex}")
            conn.rollback()
            raise
        finally:
            cursor.execute("SELECT pg_advisory_unlock(%s)", (_INIT_ADVISORY_LOCK_ID,))
            conn.close()

    def _create_tables(self, cursor):
        """Create all required tables for the database"""
        self.factions_dao.create_table(cursor)
        self.status_entries_dao.create_table(cursor)
        self.selected_snippets_dao.create_table(cursor)
        self.territory_systems_dao.create_table(cursor)
        self.target_types_dao.create_table(cursor)

    def get_factions_dao(self):
        return self.factions_dao

    def get_status_entries_dao(self):
        return self.status_entries_dao
