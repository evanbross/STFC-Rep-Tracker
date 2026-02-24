import sqlite3
from datetime import datetime
from stat_entry import StatEntry
from faction import Faction, FactionType


class Database:
    def __init__(self, db_path='stfc_rep_tracker.db'):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """Initialize the database with required tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create factions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS factions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                faction_type TEXT NOT NULL
            )
        ''')

        # Create stat_entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stat_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faction_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                value INTEGER NOT NULL,
                value_delta INTEGER NOT NULL,
                FOREIGN KEY (faction_id) REFERENCES factions(id)
            )
        ''')

        # Insert default factions if they don't exist
        default_factions = [
            ('Federation', 'FED'),
            ('Klingon', 'KLI'),
            ('Romulan', 'ROM')
        ]

        for name, faction_type in default_factions:
            cursor.execute('''
                INSERT OR IGNORE INTO factions (name, faction_type)
                VALUES (?, ?)
            ''', (name, faction_type))

        conn.commit()
        conn.close()

    def add_stat_entry(self, faction_name, value):
        """Add a new stat entry for a faction"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get faction_id
        cursor.execute('SELECT id FROM factions WHERE name = ?', (faction_name,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            raise ValueError(f"Faction '{faction_name}' not found")

        faction_id = result[0]

        # Calculate delta from previous entry
        cursor.execute('''
            SELECT value FROM stat_entries
            WHERE faction_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (faction_id,))

        previous = cursor.fetchone()
        value_delta = value - previous[0] if previous else value

        # Insert new entry
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO stat_entries (faction_id, timestamp, value, value_delta)
            VALUES (?, ?, ?, ?)
        ''', (faction_id, timestamp, value, value_delta))

        conn.commit()
        conn.close()

        return {
            'timestamp': timestamp,
            'value': value,
            'value_delta': value_delta
        }

    def get_faction_entries(self, faction_name):
        """Get all stat entries for a specific faction"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT se.timestamp, se.value, se.value_delta
            FROM stat_entries se
            JOIN factions f ON se.faction_id = f.id
            WHERE f.name = ?
            ORDER BY se.timestamp ASC
        ''', (faction_name,))

        entries = []
        for row in cursor.fetchall():
            entries.append({
                'timestamp': row[0],
                'value': row[1],
                'value_delta': row[2]
            })

        conn.close()
        return entries

    def get_all_factions_with_entries(self):
        """Get all factions with their stat entries"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, name, faction_type FROM factions')
        factions = cursor.fetchall()

        result = {}
        for faction_id, name, faction_type in factions:
            cursor.execute('''
                SELECT timestamp, value, value_delta
                FROM stat_entries
                WHERE faction_id = ?
                ORDER BY timestamp ASC
            ''', (faction_id,))

            entries = []
            for row in cursor.fetchall():
                entries.append({
                    'timestamp': row[0],
                    'value': row[1],
                    'value_delta': row[2]
                })

            result[name] = entries

        conn.close()
        return result

    def get_all_factions(self):
        """Get list of all factions"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name, faction_type FROM factions')
        factions = [{'name': row[0], 'faction_type': row[1]} for row in cursor.fetchall()]

        conn.close()
        return factions
