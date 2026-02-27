import sqlite3

from app.database import stat_entries_dao, factions_dao
from app.database.reputations_dao import ReputationsDAO


class Database:

    def __init__(self, db_path="stfc_rep_tracker.db"):
        self.db_path = db_path
        self.factions_dao = factions_dao.FactionsDAO(self)
        self.factions = self.factions_dao

        self.stat_entries_dao = stat_entries_dao.StatEntriesDAO(self)
        self.stat_entries = self.stat_entries_dao

        self.init_database()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """Initialize the database with required tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create all required tables (this also handles initial data application)
        self._create_tables(cursor)

        ReputationsDAO.initialize_dao_instances(conn, self.factions_dao)

        conn.commit()
        conn.close()

    def _create_tables(self, cursor):
        """Create all required tables for the database"""
        self.factions_dao.create_table(cursor)
        self.stat_entries_dao.create_table(cursor)

    def get_factions_dao(self):
        return self.factions_dao

    def get_stat_entries_dao(self):
        return self.stat_entries_dao
