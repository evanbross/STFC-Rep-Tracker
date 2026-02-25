import sqlite3
from app.database import fkr_reputations_dao, rogue_reputations_dao, augment_reputations_dao, stat_entries_dao, factions_dao, bajoran_reputations_dao, terran_reputations_dao, dti_reputations_dao, section31_reputations_dao, ex_borg_reputations_dao


class Database:
    daos = {}

    def __init__(self, db_path='stfc_rep_tracker.db'):
        self.db_path = db_path
        self.factions = factions_dao.FactionsDAO(self)
        self.daos['factions'] = self.factions

        self.stat_entries = stat_entries_dao.StatEntriesDAO(self)
        self.fkr_reputations = fkr_reputations_dao.FKRReputationsDAO(self)
        self.augment_reputations = augment_reputations_dao.AugmentReputationsDAO(self)
        self.rogue_reputations = rogue_reputations_dao.RogueReputationsDAO(self)
        self.bajoran_reputations = bajoran_reputations_dao.BajoranReputationsDAO(self)
        self.terran_reputations = terran_reputations_dao.TerranReputationsDAO(self)
        self.dti_reputations = dti_reputations_dao.DTIReputationsDAO(self)
        self.section31_reputations = section31_reputations_dao.Section31ReputationsDAO(self)
        self.ex_borg_reputations = ex_borg_reputations_dao.ExBorgReputationsDAO(self)
        self.init_database()

    def get_daos(self):
        return self.daos

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
        self.factions.create_table(cursor)
        self.stat_entries.create_table(cursor)
        self.fkr_reputations.create_table(cursor)
        self.augment_reputations.create_table(cursor)
        self.rogue_reputations.create_table(cursor)
        self.bajoran_reputations.create_table(cursor)
        self.terran_reputations.create_table(cursor)
        self.dti_reputations.create_table(cursor)
        self.section31_reputations.create_table(cursor)
        self.ex_borg_reputations.create_table(cursor)
