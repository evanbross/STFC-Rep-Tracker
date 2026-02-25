
def create_table(cursor):
    """Create bajoran_reputations table and handle migrations"""
    # Migration: Check if old table exists and rename it
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='BajoranReputations'")
    if cursor.fetchone():
        cursor.execute("ALTER TABLE BajoranReputations RENAME TO bajoran_reputations")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bajoran_reputations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT NOT NULL UNIQUE,
            low_limit INTEGER NOT NULL,
            high_limit INTEGER
        )
    ''')
    
    # Apply initial bajoran reputations
    apply_initial_bajoran_reputations(cursor)

def get_all_bajoran_reputations(db):
    """Get list of all bajoran reputations from bajoran_reputations table"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id, Name, low_limit, high_limit FROM bajoran_reputations ORDER BY low_limit')
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

def apply_initial_bajoran_reputations(cursor):
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
