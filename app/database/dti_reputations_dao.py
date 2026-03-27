
from app.database.reputations_dao import ReputationsDAO

class DTIReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'dti_reputations')

    def create_table(self, cursor):
        """Create dti_reputations table and handle migrations"""
        cursor.execute("PRAGMA table_info('dti_reputations')")
        columns = [row[1].lower() for row in cursor.fetchall()]

        # Migrate reputation_name → name if needed
        if "reputation_name" in columns and "name" not in columns:
            cursor.execute("ALTER TABLE dti_reputations RENAME COLUMN reputation_name TO name")
            columns = [c if c != "reputation_name" else "name" for c in columns]

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dti_reputations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                low_limit INTEGER NOT NULL,
                high_limit INTEGER,
                messages_count INTEGER NOT NULL,
                credit_amount INTEGER NOT NULL
            )
        ''')

        # Add high_limit column if missing (migration for existing tables)
        if "high_limit" not in columns:
            cursor.execute("ALTER TABLE dti_reputations ADD COLUMN high_limit INTEGER")

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
            cursor.execute("DELETE FROM dti_reputations WHERE name = ?", (obsolete,))
        for name, low_limit, high_limit, messages_count, credit_amount in self.get_initial_reputations():
            cursor.execute('''
                INSERT OR IGNORE INTO dti_reputations (name, low_limit, high_limit, messages_count, credit_amount)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, low_limit, high_limit, messages_count, credit_amount))

            cursor.execute('''
                UPDATE dti_reputations
                SET low_limit = ?, high_limit = ?, messages_count = ?, credit_amount = ?
                WHERE name = ?
            ''', (low_limit, high_limit, messages_count, credit_amount, name))
