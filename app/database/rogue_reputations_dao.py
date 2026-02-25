
from app.database.reputations_dao import ReputationsDAO

class RogueReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'rogue_reputations')

    def create_table(self, cursor):
        """Create rogue_reputations table and handle migrations"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rogue_reputations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL UNIQUE,
                low_limit INTEGER NOT NULL,
                high_limit INTEGER
            )
        ''')
        
        # Apply initial rogue reputations
        self.apply_initial_rogue_reputations(cursor)


    def apply_initial_rogue_reputations(self, cursor):
        """Apply initial rogue reputation levels to the rogue_reputations table"""
        initial_reputations = [
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
        
        for name, low_limit, high_limit in initial_reputations:
            # Try to insert
            cursor.execute('''
                INSERT OR IGNORE INTO rogue_reputations (Name, low_limit, high_limit)
                VALUES (?, ?, ?)
            ''', (name, low_limit, high_limit))
            
            # Update values if it already exists (ensures data matches requirements)
            cursor.execute('''
                UPDATE rogue_reputations 
                SET low_limit = ?, high_limit = ? 
                WHERE Name = ?
            ''', (low_limit, high_limit, name))
