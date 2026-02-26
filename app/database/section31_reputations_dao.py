
from app.database.reputations_dao import ReputationsDAO

class Section31ReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'section31_reputations')

    def get_initial_reputations(self):
        """Apply initial reputation levels to the section31_reputations table"""
        return [
            ('Neutral', 0, 1000),
        ]
