
from app.database.reputations_dao import ReputationsDAO

class FKRReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'fkr_reputations')

    def get_initial_reputations(self):
        """Apply initial reputation levels to the fkr_reputations table"""
        return [
            ('Enemy', -2000000, -500000),
            ('Hostile', -500000, -25000),
            ('Untrustworthy', -25000, -500),
            ('Neutral', -500, 500),
            ('Tolerated', 500, 5000),
            ('Neighbor', 5000, 25000),
            ('Friendly', 25000, 100000),
            ('Favored', 100000, 500000),
            ('Consort', 500000, 2000000),
            ('Associate', 2000000, 10000000),
            ('Respected (Lock 1)', 10000000, 30000000),
            ('Celebrated', 30000000, 50000000),
            ('Admired', 50000000, 80000000),
            ('Esteemed', 80000000, 140000000),
            ('Commended', 140000000, 440000000),
            ('Glorified', 440000000, 1000000000),
            ('Champion (Lock 2)', 1000000000, 1100000000)
        ]
