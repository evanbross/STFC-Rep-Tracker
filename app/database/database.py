import psycopg2
from contextlib import contextmanager

from app.database import status_entries_dao, factions_dao
from app.database.faction_selected_snippets_dao import FactionSelectedSnippetsDAO
from app.database.reputations_dao import ReputationsDAO
from app.database.territory_systems_dao import TerritorySystemsDAO

# Stable advisory lock key used to serialize init_database across workers.
# Multiple Gunicorn workers can race to run init at startup; the advisory lock
# makes them queue so only one performs DDL/upserts at a time.
_INIT_ADVISORY_LOCK_ID = 0x535446435F5245


class Database:

    def __init__(self, db_url):
        self.db_url = db_url
        self.factions_dao = factions_dao.FactionsDAO(self)
        self.factions = self.factions_dao

        self.status_entries_dao = status_entries_dao.StatusEntriesDAO(self)
        self.status_entries = self.status_entries_dao

        self.selected_snippets_dao = FactionSelectedSnippetsDAO(self)
        self.selected_snippets = self.selected_snippets_dao

        self.territory_systems_dao = TerritorySystemsDAO(self)
        self.territory_systems = self.territory_systems_dao

        self.init_database()

    def get_connection(self):
        return psycopg2.connect(self.db_url)

    @contextmanager
    def connect(self):
        """Context manager that yields a connection, commits on success, rolls back on error, and always closes."""
        conn = psycopg2.connect(self.db_url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_database(self):
        """Initialize the database with required tables.

        Uses a PostgreSQL session-level advisory lock to serialize this across
        all worker processes.  Without it, multiple Gunicorn workers starting
        simultaneously can deadlock on concurrent DELETEs and upserts inside
        apply_initial_reputations.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT pg_advisory_lock(%s)", (_INIT_ADVISORY_LOCK_ID,))
        try:
            self._create_tables(cursor)
            ReputationsDAO.initialize_dao_instances(self, self.factions_dao)
            for dao in ReputationsDAO.get_all_dao_by_class_name().values():
                dao.create_table(cursor)
            conn.commit()
        finally:
            cursor.execute("SELECT pg_advisory_unlock(%s)", (_INIT_ADVISORY_LOCK_ID,))
            conn.close()

    def _create_tables(self, cursor):
        """Create all required tables for the database"""
        self.factions_dao.create_table(cursor)
        self.status_entries_dao.create_table(cursor)
        self.selected_snippets_dao.create_table(cursor)
        self.territory_systems_dao.create_table(cursor)

    def get_factions_dao(self):
        return self.factions_dao

    def get_status_entries_dao(self):
        return self.status_entries_dao