
from app.database.reputations_dao import ReputationsDAO

class BajoranReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'bajoran_reputations')

    def get_initial_reputations(self):
        """Apply initial bajoran reputation levels to the bajoran_reputations table"""
        return [
            ('Neutral', 0, 299),
            ('Tolerated', 300, 1999),
            ('Guerilla', 2000, 4999),
            ('Militia', 5000, 14999),
            ('Favored', 15000, 49999),
            ('Pagh-strong', 50000, 149999),
            ('Higa Metar', 150000, 399999),
            ('Kohn-Ma', 400000, 799999),
            ('Ornathia', 800000, 1999999),
            ('Resister', 2000000, 4999999),
            ('Prophet Chosen, Capped', 5000000, 5000500)
        ]
