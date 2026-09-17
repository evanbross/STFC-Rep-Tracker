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

class ExBorgReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'ex_borg_reputations')

    def get_initial_reputations(self):
        """Apply initial reputation levels to the ex_borg_reputations table"""
        return [
            ('Neutral', 0, 22499),
            ('Distinguished', 22500, 62999),
            ('Celebrated', 63000, 104999),
            ('Esteemed', 105000, 153999),
            ('Venerated', 154000, 204999),
            ('Exalted', 205000, 259999),
            ('Liberator', 260000, 10000000)
        ]
