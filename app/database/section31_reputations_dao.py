
from app.database.reputations_dao import ReputationsDAO

class Section31ReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'section31_reputations')

    def create_table(self, cursor):
        """Create section31_reputations table and handle migrations"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS section31_reputations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                low_limit INTEGER NOT NULL,
                high_limit INTEGER
            )
        ''')

        # Apply initial reputation levels
        self.apply_initial_section31_reputations(cursor)


    def apply_initial_section31_reputations(self, cursor):
        """Apply initial reputation levels to the section31_reputations table"""
        # Note: Using placeholder data as specific data was not provided in the issue description.
        # The structure follows the fkr_reputations model.
        initial_reputations = [
            ('Neutral', 0, 1000),
        ]
        
        for name, low_limit, high_limit in initial_reputations:
            cursor.execute('''
                INSERT OR IGNORE INTO section31_reputations (name, low_limit, high_limit)
                VALUES (?, ?, ?)
            ''', (name, low_limit, high_limit))
            
            cursor.execute('''
                UPDATE section31_reputations 
                SET low_limit = ?, high_limit = ? 
                WHERE name = ?
            ''', (low_limit, high_limit, name))
