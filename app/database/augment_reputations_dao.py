
def create_table(cursor):
    """Create augment_reputations table and handle migrations"""
    # Migration: Check if old table exists and rename it
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='AugmentReputations'")
    if cursor.fetchone():
        cursor.execute("ALTER TABLE AugmentReputations RENAME TO augment_reputations")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS augment_reputations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT NOT NULL UNIQUE,
            low_limit INTEGER NOT NULL,
            high_limit INTEGER
        )
    ''')
    
    # Apply initial augment reputations
    apply_initial_augment_reputations(cursor)

def get_all_augment_reputations(db):
    """Get list of all augment reputations from augment_reputations table"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id, Name, low_limit, high_limit FROM augment_reputations ORDER BY low_limit')
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

def apply_initial_augment_reputations(cursor):
    """Apply initial augment reputation levels to the augment_reputations table"""
    initial_reputations = [
        ('Neutral', 0, 249),
        ('Servant', 250, 2499),
        ('Pawn', 2500, 49999),
        ('Associate', 50000, 249999),
        ('Friend', 250000, 999999),
        ('Ally, Capped', 1000000, 1000500)
    ]
    
    for name, low_limit, high_limit in initial_reputations:
        # Try to insert
        cursor.execute('''
            INSERT OR IGNORE INTO augment_reputations (Name, low_limit, high_limit)
            VALUES (?, ?, ?)
        ''', (name, low_limit, high_limit))
        
        # Update values if it already exists (ensures data matches requirements)
        cursor.execute('''
            UPDATE augment_reputations 
            SET low_limit = ?, high_limit = ? 
            WHERE Name = ?
        ''', (low_limit, high_limit, name))
