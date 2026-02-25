
from app.database.reputations_dao import ReputationsDAO

class BajoranReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'bajoran_reputations')

    def create_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bajoran_reputations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL UNIQUE,
                low_limit INTEGER NOT NULL,
                high_limit INTEGER
            )
        ''')
        
        # Apply initial bajoran reputations
        self.apply_initial_bajoran_reputations(cursor)


    def apply_initial_bajoran_reputations(self, cursor):
        """Apply initial bajoran reputation levels to the bajoran_reputations table"""
        initial_reputations = [
            ('Neutral', 0, 299),
            ('Tolerated', 300, 1999),
            ('Guerilla', 2000, 4999),
            ('Militia', 5000, 14999),
            ('Favored', 15000, 49999),
            ('Pagh-strong', 50000, 149999),
            ('Higa Metar', 150000, 399999),
            ('Kohn-Ma', 400000, 799999),
            ('Ornathia', 800000, 1999999),
            ('Resister', 2000000, 4999999),
            ('Prophet Chosen, Capped', 5000000, 5000500)
        ]
        
        for name, low_limit, high_limit in initial_reputations:
            # Try to insert
            cursor.execute('''
                INSERT OR IGNORE INTO bajoran_reputations (Name, low_limit, high_limit)
                VALUES (?, ?, ?)
            ''', (name, low_limit, high_limit))
            
            # Update values if it already exists (ensures data matches requirements)
            cursor.execute('''
                UPDATE bajoran_reputations 
                SET low_limit = ?, high_limit = ? 
                WHERE Name = ?
            ''', (low_limit, high_limit, name))
