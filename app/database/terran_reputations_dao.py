# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# LICENSE: Personal Use Only
# This source code is made available for personal, non-commercial use only.
# You may read, study, and run this code for personal purposes.
# You may NOT:
#   - Use this code, in whole or in part, in any commercial product or service
#   - Sell, sublicense, or otherwise monetize this code or derivatives of it
#   - Redistribute this code without explicit written permission from ZombieTech LLC
#
# No warranty is provided, express or implied. Use at your own risk.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
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
