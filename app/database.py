import sqlite3
from datetime import datetime
from app.models.stat_entry import StatEntry
from app.models.faction import Faction
from app.models.faction_type import FactionType, FactionTypes


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

        # Create all required tables
        self._create_tables(cursor)

        # Apply initial colors to known faction types
        self._apply_initial_colors(cursor)

        # Apply initial reputations
        self._apply_initial_reputations(cursor)

        # Populate FactionTypes from database
        self._initialize_faction_types_from_db(cursor)

        # Create factions from all faction_types in the database
        cursor.execute('''
            INSERT OR IGNORE INTO factions (name, faction_type_id)
            SELECT name, id FROM faction_types
        ''')

        conn.commit()
        conn.close()

    def get_all_reputations(self):
        """Get list of all reputations"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, Name, low_limit FROM Reputations ORDER BY low_limit')
        reputations = [
            {
                'id': row[0],
                'name': row[1],
                'low_limit': row[2],
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return reputations

    def _create_tables(self, cursor):
        """Create all required tables for the database"""
        # Create faction_types table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faction_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                color TEXT
            )
        ''')

        # Ensure color exists for faction_types
        cursor.execute("PRAGMA table_info('faction_types')")
        columns = [row[1] for row in cursor.fetchall()]
        if 'color' not in columns:
            cursor.execute('ALTER TABLE faction_types ADD COLUMN color TEXT')

        # Create factions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS factions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                faction_type_id INTEGER NOT NULL,
                on_column INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (faction_type_id) REFERENCES faction_types(id)
            )
        ''')

        # Ensure on_column exists for existing databases (SQLite lacks IF NOT EXISTS for columns)
        cursor.execute("PRAGMA table_info('factions')")
        columns = [row[1] for row in cursor.fetchall()]
        if 'on_column' not in columns:
            cursor.execute('ALTER TABLE factions ADD COLUMN on_column INTEGER NOT NULL DEFAULT 0')

        # Create stat_entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stat_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faction_id INTEGER NOT NULL,
                faction_type_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                value INTEGER NOT NULL,
                value_delta INTEGER NOT NULL,
                FOREIGN KEY (faction_id) REFERENCES factions(id),
                FOREIGN KEY (faction_type_id) REFERENCES faction_types(id)
            )
        ''')

        # Create Reputations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Reputations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL UNIQUE,
                low_limit INTEGER NOT NULL
            )
        ''')

    def _apply_initial_colors(self, cursor):
        """Apply the specified colors to the faction types if they are not set"""
        initial_colors = {
            'Augment': 'gold',
            'Federation': 'royalblue',
            'Klingon': 'red',
            'Romulan': 'green',
            'Section 31': 'black' # 'shiny black' is not a standard CSS color, 'black' is closer.
        }
        
        for name, color in initial_colors.items():
            cursor.execute('''
                UPDATE faction_types 
                SET color = ? 
                WHERE name = ? AND (color IS NULL OR color = '')
            ''', (color, name))

    def _apply_initial_reputations(self, cursor):
        """Apply initial reputation levels to the Reputations table"""
        initial_reputations = [
            ('Enemy', -2000000),
            ('Hostile', -500000),
            ('Untrustworthy', -25000),
            ('Neutral', -500),
            ('Tolerated', 500),
            ('Neighbor', 5000),
            ('Friendly', 25000),
            ('Favored', 100000),
            ('Consort', 500000),
            ('Associate', 2000000),
            ('Respected (Lock 1)', 10000000),
            ('Celebrated', 30000000),
            ('Admired', 50000000),
            ('Esteemed', 80000000),
            ('Commended', 140000000),
            ('Glorified', 440000000),
            ('Champion (Lock 2)', 1000000000)
        ]
        
        for name, low_limit in initial_reputations:
            cursor.execute('''
                INSERT OR IGNORE INTO Reputations (Name, low_limit)
                VALUES (?, ?)
            ''', (name, low_limit))

    def _initialize_faction_types_from_db(self, cursor):
        """Load all faction types from database into FactionTypes.entries"""
        cursor.execute('SELECT id, code, name, color FROM faction_types')
        db_faction_types = cursor.fetchall()

        # Clear current entries and replace with data from database
        FactionTypes.entries = []
        for id, code, name, color in db_faction_types:
            FactionTypes.entries.append(FactionType(id, code, name, color))

    def add_stat_entry(self, faction_name, value):
        """Add a new stat entry for a faction"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get faction_id and faction_type_id
        cursor.execute('''
            SELECT f.id, f.faction_type_id
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
        faction_type_id = result[1]

        # Calculate delta from previous entry
        cursor.execute('''
            SELECT value FROM stat_entries
            WHERE faction_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (
            faction_id,
        ))

        previous = cursor.fetchone()
        value_delta = value - previous[0] if previous else value

        # Insert new entry
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO stat_entries (faction_id, faction_type_id, timestamp, value, value_delta)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            faction_id,
            faction_type_id,
            timestamp,
            value,
            value_delta,
        ))

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
        ''', (
            faction_name,
        ))

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

        cursor.execute('''
            SELECT f.id, f.name, ft.code
            FROM factions f
            JOIN faction_types ft ON f.faction_type_id = ft.id
        ''')
        factions = cursor.fetchall()

        result = {}
        for faction_id, name, faction_type_code in factions:
            cursor.execute('''
                SELECT timestamp, value, value_delta
                FROM stat_entries
                WHERE faction_id = ?
                ORDER BY timestamp ASC
            ''', (
                faction_id,
            ))

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

        cursor.execute('''
            SELECT f.id, f.name, ft.code, ft.id as faction_type_id, f.on_column
            FROM factions f
            JOIN faction_types ft ON f.faction_type_id = ft.id
            ORDER BY f.name
        ''')
        factions = [
            {
                'id': row[0],
                'name': row[1],
                'faction_type': row[2],
                'faction_type_id': row[3],
                'on_column': row[4],
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return factions

    def get_faction_summary(self):
        """Get summary data for all factions including latest value and delta"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT f.id, f.name, ft.code, f.on_column, ft.color
            FROM factions f
            JOIN faction_types ft ON f.faction_type_id = ft.id
            ORDER BY f.name
        ''')
        factions = cursor.fetchall()

        result = []
        for faction_id, name, faction_type_code, on_column, color in factions:
            # Get latest entries (up to 2 for calculation)
            cursor.execute('''
                SELECT value, value_delta, timestamp
                FROM stat_entries
                WHERE faction_id = ?
                ORDER BY timestamp DESC
                LIMIT 2
            ''', (faction_id,))

            entries = cursor.fetchall()
            latest = entries[0] if len(entries) > 0 else None
            previous = entries[1] if len(entries) > 1 else None

            # Get total count of entries
            cursor.execute('''
                SELECT COUNT(*)
                FROM stat_entries
                WHERE faction_id = ?
            ''', (faction_id,))
            entry_count = cursor.fetchone()[0]

            # Calculate status
            status = {
                'minutes': 0.0,
                'delta': 0,
                'value_change': 0,
                'raw_change_per_minute': 0.0,
                'avg_change_per_minute': 0.0,
                'minutes_to_goal': 0.0
            }

            if latest and previous:
                t1 = datetime.fromisoformat(previous[2])
                t2 = datetime.fromisoformat(latest[2])
                diff = t2 - t1
                minutes = diff.total_seconds() / 60.0
                
                if minutes > 0:
                    status['minutes'] = round(minutes, 2)
                    status['delta'] = latest[0] - previous[0]
                    status['value_change'] = status['delta']
                    status['raw_change_per_minute'] = round(status['delta'] / minutes, 2)
                    # For now, avg is same as raw if we only have 2 points
                    status['avg_change_per_minute'] = status['raw_change_per_minute']
            
            result.append({
                'id': faction_id,
                'name': name,
                'faction_type': faction_type_code,
                'on_column': on_column,
                'color': color,
                'current_value': latest[0] if latest else 0,
                'last_delta': latest[1] if latest else 0,
                'last_updated': latest[2] if latest else None,
                'entry_count': entry_count,
                'status': status
            })

        conn.close()
        return result

    def add_faction(self, name, faction_type_id, on_column=0):
        """Add a new faction"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO factions (name, faction_type_id, on_column)
                VALUES (?, ?, ?)
            ''', (name, faction_type_id, on_column))

            faction_id = cursor.lastrowid
            conn.commit()

            # Get the faction type code for the response
            cursor.execute('SELECT code FROM faction_types WHERE id = ?', (faction_type_id,))
            faction_type_code = cursor.fetchone()[0]

            result = {
                'id': faction_id,
                'name': name,
                'faction_type_id': faction_type_id,
                'faction_type': faction_type_code,
                'on_column': on_column,
            }
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Faction with name '{name}' already exists")
        except Exception as e:
            conn.close()
            raise e

        conn.close()
        return result

    def update_faction(self, id, name, faction_type_id, on_column=0):
        """Update an existing faction"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Check if faction exists
        cursor.execute('SELECT id FROM factions WHERE id = ?', (id,))
        if not cursor.fetchone():
            conn.close()
            raise ValueError(f"Faction with id {id} not found")

        try:
            cursor.execute('''
                UPDATE factions
                SET name = ?, faction_type_id = ?, on_column = ?
                WHERE id = ?
            ''', (name, faction_type_id, on_column, id))

            conn.commit()

            # Get the faction type code for the response
            cursor.execute('SELECT code FROM faction_types WHERE id = ?', (faction_type_id,))
            faction_type_code = cursor.fetchone()[0]

            result = {
                'id': id,
                'name': name,
                'faction_type_id': faction_type_id,
                'faction_type': faction_type_code,
                'on_column': on_column,
            }
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Faction with name '{name}' already exists")
        except Exception as e:
            conn.close()
            raise e

        conn.close()
        return result

    def get_all_faction_types(self):
        """Get list of all faction types"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, code, name, color FROM faction_types ORDER BY name')
        faction_types = [
            {
                'id': row[0],
                'code': row[1],
                'name': row[2],
                'color': row[3],
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return faction_types

    def add_faction_type(self, code, name, color=None):
        """Add a new faction type"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO faction_types (code, name, color)
                VALUES (?, ?, ?)
            ''', (code, name, color))

            faction_type_id = cursor.lastrowid

            # Create corresponding faction
            cursor.execute('''
                INSERT INTO factions (name, faction_type_id)
                VALUES (?, ?)
            ''', (name, faction_type_id))

            conn.commit()

            result = {
                'id': faction_type_id,
                'code': code,
                'name': name,
                'color': color
            }
        except sqlite3.IntegrityError as e:
            conn.close()
            raise ValueError(f"Faction type with code '{code}' already exists")

        conn.close()
        return result

    def update_faction_type(self, id, code, name, color=None):
        """Update an existing faction type"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Check if faction type exists
        cursor.execute('SELECT id FROM faction_types WHERE id = ?', (id,))
        if not cursor.fetchone():
            conn.close()
            raise ValueError(f"Faction type with id {id} not found")

        try:
            cursor.execute('''
                UPDATE faction_types
                SET code = ?, name = ?, color = ?
                WHERE id = ?
            ''', (code, name, color, id))

            # Update corresponding faction name
            cursor.execute('''
                UPDATE factions
                SET name = ?
                WHERE faction_type_id = ?
            ''', (name, id))

            conn.commit()

            result = {
                'id': id,
                'code': code,
                'name': name,
                'color': color
            }
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Faction type with code '{code}' already exists")

        conn.close()
        return result
