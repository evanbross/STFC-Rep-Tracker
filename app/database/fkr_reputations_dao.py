
from app.database.reputations_dao import ReputationsDAO

class FKRReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'fkr_reputations')

    def create_table(self, cursor):
        """Create fkr_reputations table and handle migrations"""
        # Create fkr_reputations table (formerly Reputations)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Reputations'")
        if cursor.fetchone():
            cursor.execute('ALTER TABLE Reputations RENAME TO fkr_reputations')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fkr_reputations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL UNIQUE,
                low_limit INTEGER NOT NULL,
                high_limit INTEGER
            )
        ''')

        # Ensure high_limit exists for fkr_reputations
        cursor.execute("PRAGMA table_info('fkr_reputations')")
        columns = [row[1] for row in cursor.fetchall()]
        if 'high_limit' not in columns:
            cursor.execute('ALTER TABLE fkr_reputations ADD COLUMN high_limit INTEGER')

        # Apply initial reputation levels
        self.apply_initial_fkr_reputations(cursor)


    def apply_initial_fkr_reputations(self, cursor):
        """Apply initial reputation levels to the fkr_reputations table"""
        initial_reputations = [
            ('Enemy', -2000000, -500000),
            ('Hostile', -500000, -25000),
            ('Untrustworthy', -25000, -500),
            ('Neutral', -500, 500),
            ('Tolerated', 500, 5000),
            ('Neighbor', 5000, 25000),
            ('Friendly', 25000, 100000),
            ('Favored', 100000, 500000),
            ('Consort', 500000, 2000000),
            ('Associate', 2000000, 10000000),
            ('Respected (Lock 1)', 10000000, 30000000),
            ('Celebrated', 30000000, 50000000),
            ('Admired', 50000000, 80000000),
            ('Esteemed', 80000000, 140000000),
            ('Commended', 140000000, 440000000),
            ('Glorified', 440000000, 1000000000),
            ('Champion (Lock 2)', 1000000000, 1100000000)
        ]
        
        for name, low_limit, high_limit in initial_reputations:
            # Try to insert
            cursor.execute('''
                INSERT OR IGNORE INTO fkr_reputations (Name, low_limit, high_limit)
                VALUES (?, ?, ?)
            ''', (name, low_limit, high_limit))
            
            # Update high_limit if it's currently NULL or different (for existing records)
            cursor.execute('''
                UPDATE fkr_reputations 
                SET high_limit = ? 
                WHERE Name = ? AND (high_limit IS NULL OR high_limit != ?)
            ''', (high_limit, name, high_limit))
