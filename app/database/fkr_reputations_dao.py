
from app.database.reputations_dao import ReputationsDAO

class FKRReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'fkr_reputations')

    def get_initial_reputations(self):
        """Apply initial reputation levels to the fkr_reputations table"""
        return [
            ('Enemy',              -2000000,   -500000),
            ('Hostile',             -499999,    -25000),
            ('Untrustworthy',        -24999,      -500),
            ('Neutral',                -499,       499),
            ('Tolerated',               500,      4999),
            ('Neighbor',              5000,      25000),
            ('Friendly',             25000,      99999),
            ('Favored',             100000,     499999),
            ('Consort I',           500000,    1199999),
            ('Consort II',         1200000,    1999999),
            ('Associate I',        2000000,    4999999),
            ('Associate II',       5000000,    9999999),
            ('Respected (Lock 1)', 10000000,  29999999),
            ('Celebrated',         30000000,  49999999),
            ('Admired',            50000000,  79999999),
            ('Esteemed',           80000000, 139999999),
            ('Commended',         140000000, 339999999),
            ('Glorified',         440000000, 999999999),
            ('Champion (Lock 2)', 1000000000, 1099999999),
        ]

    def apply_initial_reputations(self, cursor):
        # Remove obsolete rows that were split into sub-tiers
        for obsolete in ('Consort', 'Associate'):
            cursor.execute(
                "DELETE FROM fkr_reputations WHERE name = ?",
                (obsolete,),
            )
        super().apply_initial_reputations(cursor)
