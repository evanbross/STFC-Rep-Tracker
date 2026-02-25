import sqlite3
from app.database import fkr_reputations_dao, rogue_reputations_dao, augment_reputations_dao, stat_entries_dao, factions_dao, bajoran_reputations_dao, terran_reputations_dao, dti_reputations_dao, section31_reputations_dao, ex_borg_reputations_dao


class Database:
    def __init__(self, db_path='stfc_rep_tracker.db'):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """Initialize the database with required tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create all required tables (this also handles initial data application)
        self._create_tables(cursor)

        conn.commit()
        conn.close()

    def _create_tables(self, cursor):
        """Create all required tables for the database"""
        factions_dao.create_table(cursor)
        stat_entries_dao.create_table(cursor)
        fkr_reputations_dao.create_table(cursor)
        augment_reputations_dao.create_table(cursor)
        rogue_reputations_dao.create_table(cursor)
        bajoran_reputations_dao.create_table(cursor)
        terran_reputations_dao.create_table(cursor)
        dti_reputations_dao.create_table(cursor)
        section31_reputations_dao.create_table(cursor)
        ex_borg_reputations_dao.create_table(cursor)
