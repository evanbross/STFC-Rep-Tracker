
from app.database.reputations_dao import ReputationsDAO

class AugmentReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'augment_reputations')

    def get_initial_reputations(self):
        """Apply initial augment reputation levels to the augment_reputations table"""
        return [
            ('Neutral', 0, 249),
            ('Servant', 250, 2499),
            ('Pawn', 2500, 49999),
            ('Associate', 50000, 249999),
            ('Friend', 250000, 999999),
            ('Ally, Capped', 1000000, 1000500)
        ]
