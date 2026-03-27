from app.database.reputations_dao import ReputationsDAO


class FKRReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, "fkr_reputations")

    def get_initial_reputations(self):
        """Apply initial reputation levels to the fkr_reputations table.
        Source: https://star-trek-fleet-command.fandom.com/wiki/Faction_Reputation
        """
        return [
            ("Enemy", -2000000, -500000),
            ("Hostile", -499999, -25000),
            ("Untrustworthy", -24999, -500),
            ("Neutral", -499, 499),
            ("Tolerated", 500, 4999),
            ("Neighbor", 5000, 24999),
            ("Friendly", 25000, 99999),
            ("Favored", 100000, 499999),
            ("Consort I", 500000, 1199999),
            ("Consort II", 1200000, 1999999),
            ("Associate I", 2000000, 4999999),
            ("Associate II", 5000000, 9999999),
            ("Respected", 10000000, 29999999),
            ("Celebrated", 30000000, 49999999),
            ("Admired", 50000000, 79999999),
            ("Esteemed", 80000000, 139999999),
            ("Commended", 140000000, 439999999),
            ("Glorified", 440000000, 999999999),
            ("Champion (lock2)", 1000000000, 1099999999),
            ("Distinguished", 1100000000, 1499000000),
            ("Guardian", 1500000000, 2399000000),
            ("Leader", 2400000000, 4399000000),
            ("Pioneer", 4400000000, 7999000000),
            ("Icon", 8100000000, 14999000000),
            ("Legend I (lock3)", 15000000000, 15999999999),
            ("Legend II", 16000000000, 16999999999),
            ("Dignitary", 17000000000, 42999999999),
            ("Renowned", 43000000000, 92999999999),
            ("Venerated", 93000000000, 181999999999),
            ("Revered", 182000000000, 314999999999),
            ("Idolized", 315000000000, 499999999999),
            ("Hero, Capped (lock4)", 500000000000, 500000000500),
        ]

    def apply_initial_reputations(self, cursor):
        # Remove obsolete rows that were renamed or split
        for obsolete in (
            "Consort",
            "Associate",  # split into I/II
            "Legend (Lock 3)",  # split into Legend I/II
        ):
            cursor.execute(
                "DELETE FROM fkr_reputations WHERE name = ?",
                (obsolete,),
            )
        super().apply_initial_reputations(cursor)
