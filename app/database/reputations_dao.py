import importlib
from abc import ABC, abstractmethod


class ReputationsDAO:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        db.get_daos()[table_name] = self

    def get_all(self):
        """Get list of all reputations from the table"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            # Most reputation tables use 'Name', but some might use 'name' or 'reputation_name'
            # We'll try to be smart about it
            cursor.execute(f"PRAGMA table_info('{self.table_name}')")
            columns = [row[1].lower() for row in cursor.fetchall()]

            name_col = 'Name'
            if 'reputation_name' in columns:
                name_col = 'reputation_name'
            elif 'name' in columns:
                name_col = 'name'

            query = f'SELECT id, {name_col}, low_limit, high_limit FROM {self.table_name} ORDER BY low_limit'

            # Check if high_limit exists (DTI doesn't have it, but has other columns)
            if 'high_limit' not in columns:
                if 'messages_count' in columns and 'credit_amount' in columns:
                    query = f'SELECT id, {name_col}, low_limit, messages_count, credit_amount FROM {self.table_name} ORDER BY low_limit'
                    cursor.execute(query)
                    reputations = [
                        {
                            'id': row[0],
                            'name': row[1],
                            'low_limit': row[2],
                            'messages_count': row[3],
                            'credit_amount': row[4],
                        }
                        for row in cursor.fetchall()
                    ]
                else:
                    # Fallback for tables without high_limit
                    query = f'SELECT id, {name_col}, low_limit FROM {self.table_name} ORDER BY low_limit'
                    cursor.execute(query)
                    reputations = [
                        {
                            'id': row[0],
                            'name': row[1],
                            'low_limit': row[2],
                            'high_limit': None,
                        }
                        for row in cursor.fetchall()
                    ]
            else:
                cursor.execute(query)
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
        except Exception as e:
            conn.close()
            raise ValueError(f"Error fetching reputations from {self.table_name}: {e}")

    def create_table(self, cursor):
        """Create augment_reputations table and handle migrations"""
        cursor.execute(f'''
                       CREATE TABLE IF NOT EXISTS {self.table_name}
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           Name TEXT NOT NULL UNIQUE,
                           low_limit INTEGER NOT NULL,
                           high_limit INTEGER
                       )
                ''')

        # Apply initial augment reputations
        self.apply_initial_reputations(cursor)


    @abstractmethod
    def get_initial_reputations(self):
        pass

    def apply_initial_reputations(self, cursor):
        for name, low_limit, high_limit in self.get_initial_reputations():
            # Try to insert
            cursor.execute(f'''
                           INSERT
                           OR IGNORE INTO
                           {self.table_name}
                           (
                           Name,
                           low_limit,
                           high_limit
                           )
                           VALUES
                           (
                           ?,
                           ?,
                           ?
                           )
                           ''', (name, low_limit, high_limit))

            # Update values if it already exists (ensures data matches requirements)
            cursor.execute(f'''
                           UPDATE {self.table_name}
                           SET low_limit  = ?,
                               high_limit = ?
                           WHERE Name = ?
                           ''', (low_limit, high_limit, name))
