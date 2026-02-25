
def create_table(cursor):
    """Create terran_reputations table and handle migrations"""
    # Migration: Check if old table exists and rename it
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TerranReputations'")
    if cursor.fetchone():
        cursor.execute("ALTER TABLE TerranReputations RENAME TO terran_reputations")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS terran_reputations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT NOT NULL UNIQUE,
            low_limit INTEGER NOT NULL,
            high_limit INTEGER
        )
    ''')
    
    # Apply initial terran reputations
    apply_initial_terran_reputations(cursor)

def get_all_terran_reputations(db):
    """Get list of all terran reputations from terran_reputations table"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id, Name, low_limit, high_limit FROM terran_reputations ORDER BY low_limit')
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

def apply_initial_terran_reputations(cursor):
    """Apply initial terran reputation levels to the terran_reputations table"""
    initial_reputations = [
        ('Outsider', 0, 179),
        ('Lackey', 180, 899),
        ('Collaborator', 900, 2699),
        ('Comrade', 2700, 4049),
        ('Ally', 4050, 6499),
        ('Valued', 6500, 10799),
        ('Lauded', 10800, 14399),
        ('Venerated', 14400, 17999),
        ('Exhalted', 18000, 22499),
        ('Renowned', 22500, 23000)
    ]
    
    for name, low_limit, high_limit in initial_reputations:
        # Try to insert
        cursor.execute('''
            INSERT OR IGNORE INTO terran_reputations (Name, low_limit, high_limit)
            VALUES (?, ?, ?)
        ''', (name, low_limit, high_limit))
        
        # Update values if it already exists (ensures data matches requirements)
        cursor.execute('''
            UPDATE terran_reputations 
            SET low_limit = ?, high_limit = ? 
            WHERE Name = ?
        ''', (low_limit, high_limit, name))
