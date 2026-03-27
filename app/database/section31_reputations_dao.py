
from app.database.reputations_dao import ReputationsDAO

class Section31ReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'section31_reputations')

    def get_initial_reputations(self):
        """Apply initial reputation levels to the section31_reputations table"""
        return [
            ('Asset',        0,       4999),
            ('Friendly',     5000,    9999),
            ('Infiltrator',  15000,   34999),
            ('Agent',        35000,   145999),
            ('Spymaster',    150000,  50000000),
        ]

    def apply_initial_reputations(self, cursor):
        # Remove stale placeholder row that was superseded by Asset
        cursor.execute("DELETE FROM section31_reputations WHERE name = 'Neutral'")
        super().apply_initial_reputations(cursor)
