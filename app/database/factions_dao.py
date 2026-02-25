import sqlite3
from datetime import datetime

def create_table(cursor):
    """Create factions table and handle migrations"""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS factions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            on_chart INTEGER NOT NULL DEFAULT 0,
            display_order INTEGER,
            on_column INTEGER NOT NULL DEFAULT 0,
            code TEXT,
            color TEXT,
            reputation_table_name TEXT
        )
    ''')

    # Ensure required columns exist for existing databases
    cursor.execute("PRAGMA table_info('factions')")
    columns = [row[1] for row in cursor.fetchall()]
    if 'on_chart' not in columns:
        cursor.execute('ALTER TABLE factions ADD COLUMN on_chart INTEGER NOT NULL DEFAULT 0')
    if 'display_order' not in columns:
        cursor.execute('ALTER TABLE factions ADD COLUMN display_order INTEGER')
    if 'on_column' not in columns:
        cursor.execute('ALTER TABLE factions ADD COLUMN on_column INTEGER NOT NULL DEFAULT 0')
    if 'code' not in columns:
        cursor.execute('ALTER TABLE factions ADD COLUMN code TEXT')
    if 'color' not in columns:
        cursor.execute('ALTER TABLE factions ADD COLUMN color TEXT')
    if 'reputation_table_name' not in columns:
        cursor.execute('ALTER TABLE factions ADD COLUMN reputation_table_name TEXT')

def get_all_factions(db):
    """Get list of all factions"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT f.id, f.name, f.code, f.on_chart, f.color, f.reputation_table_name, f.display_order, f.on_column
        FROM factions f
        ORDER BY f.display_order
    ''')
    factions = [
        {
            'id': row[0],
            'name': row[1],
            'code': row[2],
            'on_chart': row[3],
            'color': row[4],
            'reputation_table_name': row[5],
            'display_order': row[6],
            'on_column': row[7],
            'faction_type': row[2], # Map code to faction_type for compatibility
        }
        for row in cursor.fetchall()
    ]

    conn.close()
    return factions

def add_faction(db, name, code, color=None, reputation_table_name=None, on_chart=0, display_order=None, on_column=0):
    """Add a new faction"""
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO factions (name, code, color, reputation_table_name, on_chart, display_order, on_column)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, code, color, reputation_table_name, on_chart, display_order, on_column))

        faction_id = cursor.lastrowid
        conn.commit()

        result = {
            'id': faction_id,
            'name': name,
            'code': code,
            'color': color,
            'reputation_table_name': reputation_table_name,
            'on_chart': on_chart,
            'display_order': display_order,
            'on_column': on_column,
            'faction_type': code,
        }
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Faction with name '{name}' already exists")
    except Exception as e:
        conn.close()
        raise e

    conn.close()
    return result

def update_faction(db, id, name, code, color=None, reputation_table_name=None, on_chart=0, display_order=None, on_column=0):
    """Update an existing faction"""
    conn = db.get_connection()
    cursor = conn.cursor()

    # Check if faction exists
    cursor.execute('SELECT id FROM factions WHERE id = ?', (id,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError(f"Faction with id {id} not found")

    try:
        cursor.execute('''
            UPDATE factions
            SET name = ?, code = ?, color = ?, reputation_table_name = ?, on_chart = ?, display_order = ?, on_column = ?
            WHERE id = ?
        ''', (name, code, color, reputation_table_name, on_chart, display_order, on_column, id))

        conn.commit()

        result = {
            'id': id,
            'name': name,
            'code': code,
            'color': color,
            'reputation_table_name': reputation_table_name,
            'on_chart': on_chart,
            'display_order': display_order,
            'on_column': on_column,
            'faction_type': code,
        }
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Faction with name '{name}' already exists")
    except Exception as e:
        conn.close()
        raise e

    conn.close()
    return result


def get_faction_summary(db):
    """Get summary data for all factions including latest value and delta"""
    conn = db.get_connection()
    cursor = conn.cursor()

    # Get all reputations to find current level
    cursor.execute('SELECT Name, low_limit, high_limit FROM fkr_reputations')
    reputations_general = cursor.fetchall()
    
    cursor.execute('SELECT Name, low_limit, high_limit FROM augment_reputations')
    reputations_augment = cursor.fetchall()

    cursor.execute('SELECT Name, low_limit, high_limit FROM rogue_reputations')
    reputations_rogue = cursor.fetchall()

    cursor.execute('''
        SELECT f.id, f.name, f.code, f.on_chart, f.color, f.reputation_table_name, f.display_order
        FROM factions f
        ORDER BY f.display_order
    ''')
    factions_list = cursor.fetchall()

    result = []
    for faction_id, name, faction_type_code, on_chart, color, reputation_table_name, display_order in factions_list:
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

        current_value = latest[0] if latest else 0
        
        # Use appropriate reputations list
        reputations = reputations_general
        if reputation_table_name == 'AugmentReputations' or name == 'Augment':
            reputations = reputations_augment
        elif reputation_table_name == 'RogueReputations' or name == 'Rogue':
            reputations = reputations_rogue
        elif reputation_table_name == 'fkr_reputations' or reputation_table_name == 'Reputations':
            reputations = reputations_general

        # Find current reputation level
        rep_level = "Unknown"
        if latest: # Only set if there's at least one entry
            for rep_name, low_limit, high_limit in reputations:
                if high_limit is not None:
                    if low_limit <= current_value <= high_limit:
                        rep_level = rep_name
                        break
                else:
                    if current_value >= low_limit:
                        rep_level = rep_name
                        break
        
        # Special case for the very last tier if the value is exactly the high_limit
        # or if it's beyond the last tier's high limit
        if latest and rep_level == "Unknown":
            # Fallback to the previous logic or find the highest tier
            sorted_reps = sorted(reputations, key=lambda x: x[1], reverse=True)
            for rep_name, low_limit, high_limit in sorted_reps:
                if current_value >= low_limit:
                    rep_level = rep_name
                    break

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
            'on_chart': on_chart,
            'display_order': display_order,
            'color': color,
            'current_value': current_value,
            'rep_level': rep_level,
            'last_delta': latest[1] if latest else 0,
            'last_updated': latest[2] if latest else None,
            'entry_count': entry_count,
            'status': status
        })

    conn.close()
    return result
