from datetime import datetime


class StatEntriesDAO:
    def __init__(self, db):
        self.db = db

    def create_table(self, cursor):
        """Create stat_entries table"""
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS stat_entries
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           faction_id
                           INTEGER
                           NOT
                           NULL,
                           timestamp
                           TEXT
                           NOT
                           NULL,
                           value
                           INTEGER
                           NOT
                           NULL,
                           value_delta
                           INTEGER
                           NOT
                           NULL,
                           FOREIGN
                           KEY
                       (
                           faction_id
                       ) REFERENCES factions
                       (
                           id
                       )
                           )
                       ''')

    def add_stat_entry(self, faction_name, value):
        """Add a new stat entry for a faction"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get faction_id
        cursor.execute('''
                       SELECT f.id
                       FROM factions f
                       WHERE f.name = ?
                       ''', (
                           faction_name,
                       ))
        result = cursor.fetchone()

        if not result:
            conn.close()
            raise ValueError(f"Faction '{faction_name}' not found")

        faction_id = result[0]

        # Calculate delta from previous entry
        # cursor.execute('''
        #     SELECT value FROM stat_entries
        #     WHERE faction_id = ?
        #     ORDER BY timestamp DESC
        #     LIMIT 1
        # ''', (
        #     faction_id,
        # ))
        #
        # previous = cursor.fetchone()
        # value_delta = value - previous[0] if previous else value

        # Insert new entry
        timestamp = datetime.now().isoformat()
        cursor.execute('''
                       INSERT INTO stat_entries (faction_id, timestamp, value)
                       VALUES (?, ?, ?)
                       ''', (
                           faction_id,
                           timestamp,
                           value,
                       ))

        conn.commit()
        conn.close()

        return {
            'faction_id': faction_id,
            'timestamp': timestamp,
            'value': value  # ,
        }

    def get_faction_entries(self, faction_name):
        """Get all stat entries for a specific faction"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT se.timestamp, se.value, se.value_delta, se.faction_id
                       FROM stat_entries se
                                JOIN factions f ON se.faction_id = f.id
                       WHERE f.name = ?
                       ORDER BY se.timestamp ASC
                       ''', (
                           faction_name,
                       ))

        entries = []
        for row in cursor.fetchall():
            entries.append({
                'timestamp': row[0],
                'value': row[1],
                'value_delta': row[2],
                'faction_id': row[3]
            })

        conn.close()
        return entries

    def get_all_factions_with_entries(self):
        """Get all factions with their stat entries"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT f.id, f.name
                       FROM factions f
                       ''')
        factions = cursor.fetchall()

        result = {}
        for faction_id, name in factions:
            cursor.execute('''
                           SELECT timestamp, value, faction_id
                           FROM stat_entries
                           WHERE faction_id = ?
                           ORDER BY id DESC
                               LIMIT 2
                           ''', (
                               faction_id,
                           ))

            entries = []
            rows = cursor.fetchall()
            if len(rows) >= 2:
                latest_row = rows[0]
                prev_row = rows[1]
                entries.append({
                    'timestamp': latest_row[0],
                    'value': latest_row[1],
                    'faction_id': latest_row[2]
                })

            result[name] = entries

        conn.close()
        return result
