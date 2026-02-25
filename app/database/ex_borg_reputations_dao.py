
def create_table(cursor):
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
    apply_initial_ex_borg_reputations(cursor)

def get_all_ex_borg_reputations(db):
    """Get list of all reputations from ex_borg_reputations table"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id, Name, low_limit, high_limit FROM ex_borg_reputations ORDER BY low_limit')
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

def apply_initial_ex_borg_reputations(cursor):
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
