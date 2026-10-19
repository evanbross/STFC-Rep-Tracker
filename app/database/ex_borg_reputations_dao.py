# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
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
