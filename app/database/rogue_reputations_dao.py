
def create_table(cursor):
    """Create rogue_reputations table and handle migrations"""
    # Migration: Check if old table exists and rename it
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='RogueReputations'")
    if cursor.fetchone():
        cursor.execute("ALTER TABLE RogueReputations RENAME TO rogue_reputations")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rogue_reputations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT NOT NULL UNIQUE,
            low_limit INTEGER NOT NULL,
            high_limit INTEGER
        )
    ''')
    
    # Apply initial rogue reputations
    apply_initial_rogue_reputations(cursor)

def get_all_rogue_reputations(db):
    """Get list of all rogue reputations from rogue_reputations table"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id, Name, low_limit, high_limit FROM rogue_reputations ORDER BY low_limit')
    reputations = [
        {
            'id': row[0],
            'name': row[1],
            'low_limit': row[2],
            'high_limit': row[3],
        }
        for row in cursor.fetchall()
    ]

    conn.close()
    return reputations

def apply_initial_rogue_reputations(cursor):
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
