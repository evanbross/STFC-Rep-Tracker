
from app.database.reputations_dao import ReputationsDAO

class ExBorgReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'ex_borg_reputations')

    def create_table(self, cursor):
        """Create ex_borg_reputations table and handle migrations"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ex_borg_reputations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL UNIQUE,
                low_limit INTEGER NOT NULL,
                high_limit INTEGER
            )
        ''')

        # Apply initial reputation levels
        self.apply_initial_ex_borg_reputations(cursor)


    def apply_initial_ex_borg_reputations(self, cursor):
        """Apply initial reputation levels to the ex_borg_reputations table"""
        initial_reputations = [
            ('Neutral', 0, 1000) # Placeholder as specific data was not provided
        ]
        
        for name, low_limit, high_limit in initial_reputations:
            # Try to insert
            cursor.execute('''
                INSERT OR IGNORE INTO ex_borg_reputations (Name, low_limit, high_limit)
                VALUES (?, ?, ?)
            ''', (name, low_limit, high_limit))
            
            # Update high_limit if it's currently NULL or different (for existing records)
            cursor.execute('''
                UPDATE ex_borg_reputations 
                SET high_limit = ? 
                WHERE Name = ? AND (high_limit IS NULL OR high_limit != ?)
            ''', (high_limit, name, high_limit))
