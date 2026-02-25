
def create_table(cursor):
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
    apply_initial_section31_reputations(cursor)

def get_all_section31_reputations(db):
    """Get list of all reputations from section31_reputations table"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id, name, low_limit, high_limit FROM section31_reputations ORDER BY low_limit')
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

def apply_initial_section31_reputations(cursor):
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
