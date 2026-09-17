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

class RogueReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'rogue_reputations')

    def get_initial_reputations(self):
        """Apply initial rogue reputation levels to the rogue_reputations table"""
        return [
            ('Lackey', 0, 499),
            ('Abettor', 500, 4999),
            ('Trouble Maker', 5000, 24999),
            ('Scoundrel', 25000, 99999),
            ('Accomplice', 100000, 499999),
            ('Known Associate', 500000, 1999999),
            ('Partner', 2000000, 9999999),
            ('Outlaw', 10000000, 29999999),
            ('Outlaw, Capped', 30000000, 30000500)
        ]
