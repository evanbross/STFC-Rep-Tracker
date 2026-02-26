
from app.database.reputations_dao import ReputationsDAO

class TerranReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'terran_reputations')

    def get_initial_reputations(self):
        """Apply initial terran reputation levels to the terran_reputations table"""
        return [
            ('Outsider', 0, 179),
            ('Lackey', 180, 899),
            ('Collaborator', 900, 2699),
            ('Comrade', 2700, 4049),
            ('Ally', 4050, 6499),
            ('Valued', 6500, 10799),
            ('Lauded', 10800, 14399),
            ('Venerated', 14400, 17999),
            ('Exhalted', 18000, 22499),
            ('Renowned', 22500, 23000)
        ]
