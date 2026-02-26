
from app.database.reputations_dao import ReputationsDAO

class DTIReputationsDAO(ReputationsDAO):
    def __init__(self, db):
        super().__init__(db, 'dti_reputations')

    def create_table(self, cursor):
        """Create dti_reputations table and handle migrations"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dti_reputations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reputation_name TEXT NOT NULL UNIQUE,
                low_limit INTEGER NOT NULL,
                messages_count INTEGER NOT NULL,
                credit_amount INTEGER NOT NULL
            )
        ''')
        
        # Apply initial dti reputations
        self.apply_initial_reputations(cursor)


    def get_initial_reputations(self):
        """Apply initial dti reputation levels to the dti_reputations table"""
        return [
            ('Outsider', 0, 0, 0),
            ('Consort I', 180, 20, 500000),
            ('Associate I', 240, 70, 2000000),
            ('Respected', 350, 180, 10000000),
            ('Celebrated', 420, 300, 30000000),
            ('Admired', 460, 350, 50000000),
            ('Esteemed', 520, 380, 80000000),
            ('Commended', 570, 600, 140000000),
            ('Glorified', 630, 1000, 440000000),
            ('Champion', 700, 1200, 1000000000),
            ('Distinguished', 1250, 2250, 1100000000),
            ('Guardian', 1350, 2600, 1500000000),
            ('Leader', 1475, 3000, 2400000000),
            ('Pioneer', 1550, 3350, 4400000000),
            ('Icon', 1675, 3900, 8100000000),
            ('Legend', 1800, 4500, 15000000000)
        ]

    def apply_initial_reputations(self, cursor):
        initial_reputations = self.get_initial_reputations()
        
        for name, low_limit, messages_count, credit_amount in initial_reputations:
            # Try to insert
            cursor.execute('''
                INSERT OR IGNORE INTO dti_reputations (reputation_name, low_limit, messages_count, credit_amount)
                VALUES (?, ?, ?, ?)
            ''', (name, low_limit, messages_count, credit_amount))
            
            # Update values if it already exists (ensures data matches requirements)
            cursor.execute('''
                UPDATE dti_reputations 
                SET low_limit = ?, messages_count = ?, credit_amount = ? 
                WHERE reputation_name = ?
            ''', (low_limit, messages_count, credit_amount, name))
