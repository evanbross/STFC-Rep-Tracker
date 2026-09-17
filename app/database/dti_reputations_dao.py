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

class DTIReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'dti_reputations')

    def create_table(self, cursor):
        """Create the current dti_reputations table schema."""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dti_reputations (
                id             SERIAL PRIMARY KEY,
                name           TEXT NOT NULL,
                low_limit      INTEGER NOT NULL,
                high_limit     INTEGER,
                messages_count INTEGER NOT NULL,
                credit_amount  BIGINT NOT NULL
            )
        ''')

        cursor.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS "dti_reputations_name_key" '
            'ON dti_reputations (name)'
        )
        self.apply_initial_reputations(cursor)

    def get_initial_reputations(self):
        """Apply initial dti reputation levels to the dti_reputations table.
        Tuple format: (name, low_limit, high_limit, messages_count, credit_amount)
        high_limit = next row's low_limit - 1; None for the last row.
        """
        return [
            ('Outsider',      0,    179,  0,    0),
            ('Consort I',     180,  239,  20,   500000),
            ('Associate I',   240,  349,  70,   2000000),
            ('Respected',     350,  419,  180,  10000000),
            ('Celebrated',    420,  459,  300,  30000000),
            ('Admired',       460,  519,  350,  50000000),
            ('Esteemed',      520,  569,  380,  80000000),
            ('Commended',     570,  629,  600,  140000000),
            ('Glorified',     630,  699,  1000, 440000000),
            ('Champion',      700,  1249, 1200, 1000000000),
            ('Distinguished', 1250, 1349, 2250, 1100000000),
            ('Guardian',      1350, 1474, 2600, 1500000000),
            ('Leader',        1475, 1549, 3000, 2400000000),
            ('Pioneer',       1550, 1674, 3350, 4400000000),
            ('Icon',          1675, 1799, 3900, 8100000000),
            ('Legend',        1800, None, 4500, 15000000000),
        ]

    def apply_initial_reputations(self, cursor):
        # Remove stale rows that were renamed to Consort I / Associate I
        for obsolete in ('Consort', 'Associate'):
            cursor.execute("DELETE FROM dti_reputations WHERE name = %s", (obsolete,))
        for name, low_limit, high_limit, messages_count, credit_amount in self.get_initial_reputations():
            cursor.execute('''
                INSERT INTO dti_reputations (name, low_limit, high_limit, messages_count, credit_amount)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE
                    SET low_limit      = EXCLUDED.low_limit,
                        high_limit     = EXCLUDED.high_limit,
                        messages_count = EXCLUDED.messages_count,
                        credit_amount  = EXCLUDED.credit_amount
            ''', (name, low_limit, high_limit, messages_count, credit_amount))
