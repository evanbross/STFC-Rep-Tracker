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
