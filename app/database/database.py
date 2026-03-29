import sqlite3
from contextlib import contextmanager

from app.database import status_entries_dao, factions_dao
from app.database.faction_selected_snippets_dao import FactionSelectedSnippetsDAO
from app.database.reputations_dao import ReputationsDAO


class Database:

    def __init__(self, db_path="stfc_rep_tracker.db"):
        self.db_path = db_path
        self.factions_dao = factions_dao.FactionsDAO(self)
        self.factions = self.factions_dao

        self.status_entries_dao = status_entries_dao.StatusEntriesDAO(self)
        self.status_entries = self.status_entries_dao

        self.selected_snippets_dao = FactionSelectedSnippetsDAO(self)
        self.selected_snippets = self.selected_snippets_dao

        self.init_database()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    @contextmanager
    def connect(self):
        """Context manager that yields a connection, commits on success, rolls back on error, and always closes."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_database(self):
        """Initialize the database with required tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create all required tables (this also handles initial data application)
        self._create_tables(cursor)

        ReputationsDAO.initialize_dao_instances(conn, self.factions_dao)

        for dao in ReputationsDAO.get_all_dao_by_class_name().values():
            dao.create_table(cursor)

        conn.commit()
        conn.close()

    def _create_tables(self, cursor):
        """Create all required tables for the database"""
        self.factions_dao.create_table(cursor)
        self.status_entries_dao.create_table(cursor)
        self.selected_snippets_dao.create_table(cursor)

    def get_factions_dao(self):
        return self.factions_dao

    def get_status_entries_dao(self):
        return self.status_entries_dao
