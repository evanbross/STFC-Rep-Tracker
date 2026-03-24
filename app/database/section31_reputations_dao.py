
from app.database.reputations_dao import ReputationsDAO

class Section31ReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'section31_reputations')

    def get_initial_reputations(self):
        """Apply initial reputation levels to the section31_reputations table"""
        return [
            ('Asset', 0, 4999),
            ('Friendly', 5000, 9999),
        ]
