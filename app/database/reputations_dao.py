import importlib
import logging
from abc import abstractmethod
from typing import List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s",
)
logger = logging.getLogger(__name__)


class ReputationsDAO:
    dao_instances_by_faction = {}
    dao_instances_by_class = {}

    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name

    @staticmethod
    def get_dao_by_faction_name(name):
        return ReputationsDAO.dao_instances_by_faction.get(name)

    @staticmethod
    def get_dao_by_class_name(name):
        return ReputationsDAO.dao_instances_by_class.get(name)

    @staticmethod
    def get_all_dao_by_class_name():
        return ReputationsDAO.dao_instances_by_class

    @staticmethod
    def register_dao(faction_name, dao):
        ReputationsDAO.dao_instances_by_faction[faction_name] = dao
        ReputationsDAO.dao_instances_by_class[dao.__class__.__name__] = dao

    @staticmethod
    def initialize_dao_instances(db, factions_dao):
        """Initialize all reputation DAO instances based on factions in the database"""
        # Clear existing instances to avoid duplicates if re-initialized
        ReputationsDAO.dao_instances_by_faction.clear()
        ReputationsDAO.dao_instances_by_class.clear()

        factions = factions_dao.get_all_factions()
        for faction in factions:
            rep_table_name = faction.get("reputation_table_name")
            rep_dao_name = faction.get("reputation_dao_name")
            faction_name = faction.get("name")

            if not rep_dao_name:
                continue

            # If we haven't created a DAO for this table yet, do it now
            rep_dao = ReputationsDAO.get_dao_by_class_name(rep_dao_name)
            if rep_dao is None:
                try:
                    module = importlib.import_module(
                        "app.database." + rep_table_name + "_dao"
                    )
                    dao_class = getattr(module, rep_dao_name)
                    # Instantiate the DAO. Most specialized DAOs take (db)
                    # while the base ReputationsDAO takes (db, table_name)
                    if dao_class == ReputationsDAO:
                        rep_dao = dao_class(db, rep_table_name)
                    else:
                        rep_dao = dao_class(db)
                except (ImportError, AttributeError) as e:
                    logger.error(
                        f"Failed to initialize DAO {rep_dao_name} for faction {faction_name}: {e}"
                    )
                    continue

            # Register the DAO for this specific faction name
            ReputationsDAO.register_dao(faction_name, rep_dao)

        logger.info(
            f"Initialized {len(ReputationsDAO.dao_instances_by_faction)} reputation DAO mappings"
        )

    def get_all(self, db=None, table_name: str = None) -> List[Dict[str, Any]]:
        """Get list of all reputations from the table"""
        conn = (self.db if db is None else db).get_connection()
        cursor = conn.cursor()

        table_name = self.table_name if table_name is None else table_name
        dao = self.dao_instances_by_faction.get(table_name, self)

        try:
            # Most reputation tables use 'Name', but some might use 'name' or 'reputation_name'
            # We'll try to be smart about it
            cursor.execute(f"PRAGMA table_info('{table_name}')")
            columns = [row[1].lower() for row in cursor.fetchall()]

            name_col = "Name"
            if "reputation_name" in columns:
                name_col = "reputation_name"
            elif "name" in columns:
                name_col = "name"

            query = f"SELECT id, {name_col}, low_limit, high_limit FROM {table_name} ORDER BY low_limit"

            # Check if high_limit exists (DTI doesn't have it, but has other columns)
            if "high_limit" not in columns:
                if "messages_count" in columns and "credit_amount" in columns:
                    query = f"SELECT id, {name_col}, low_limit, messages_count, credit_amount FROM {table_name} ORDER BY low_limit"
                    cursor.execute(query)
                    reputations = [
                        {
                            "id": row[0],
                            "name": row[1],
                            "low_limit": row[2],
                            "messages_count": row[3],
                            "credit_amount": row[4],
                        }
                        for row in cursor.fetchall()
                    ]
                else:
                    # Fallback for tables without high_limit
                    query = f"SELECT id, {name_col}, low_limit FROM {table_name} ORDER BY low_limit"
                    cursor.execute(query)
                    reputations = [
                        {
                            "id": row[0],
                            "name": row[1],
                            "low_limit": row[2],
                            "high_limit": None,
                        }
                        for row in cursor.fetchall()
                    ]
            else:
                cursor.execute(query)
                reputations = [
                    {
                        "id": row[0],
                        "name": row[1],
                        "low_limit": row[2],
                        "high_limit": row[3],
                    }
                    for row in cursor.fetchall()
                ]

            conn.close()
            return reputations
        except Exception as e:
            conn.close()
            raise ValueError(f"Error fetching reputations from {table_name}: {e}")

    def create_table(self, cursor):
        """Create reputation table and handle migrations"""
        # We try to use a case-insensitive check for the name column
        cursor.execute(f"PRAGMA table_info('{self.table_name}')")
        columns = [row[1].lower() for row in cursor.fetchall()]

        name_col = "Name"
        if "reputation_name" in columns:
            name_col = "reputation_name"
        elif "name" in columns:
            name_col = "name"

        cursor.execute(f"""
                       CREATE TABLE IF NOT EXISTS {self.table_name}
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           {name_col} TEXT NOT NULL UNIQUE,
                           low_limit INTEGER NOT NULL,
                           high_limit INTEGER
                       )
                """)

        # Apply initial reputations
        self.apply_initial_reputations(cursor)

    @abstractmethod
    def get_initial_reputations(self):
        pass

    def apply_initial_reputations(self, cursor):
        # We try to use a case-insensitive check for the name column
        cursor.execute(f"PRAGMA table_info('{self.table_name}')")
        columns = [row[1].lower() for row in cursor.fetchall()]

        name_col = "Name"
        if "reputation_name" in columns:
            name_col = "reputation_name"
        elif "name" in columns:
            name_col = "name"

        # Check if high_limit exists (some special tables like DTI might not have it yet or at all)
        has_high_limit = "high_limit" in columns

        for entry in self.get_initial_reputations():
            if has_high_limit and len(entry) >= 3:
                name, low_limit, high_limit = entry[0], entry[1], entry[2]
                # Try to insert
                cursor.execute(
                    f"""
                               INSERT OR IGNORE INTO {self.table_name} ({name_col}, low_limit, high_limit)
                               VALUES (?, ?, ?)
                               """,
                    (name, low_limit, high_limit),
                )

                # Update values if it already exists
                cursor.execute(
                    f"""
                               UPDATE {self.table_name}
                               SET low_limit  = ?,
                                   high_limit = ?
                               WHERE {name_col} = ?
                               """,
                    (low_limit, high_limit, name),
                )
            else:
                # Handle cases with fewer columns or missing high_limit
                name, low_limit = entry[0], entry[1]
                cursor.execute(
                    f"""
                               INSERT OR IGNORE INTO {self.table_name} ({name_col}, low_limit)
                               VALUES (?, ?)
                               """,
                    (name, low_limit),
                )
                cursor.execute(
                    f"""
                               UPDATE {self.table_name}
                               SET low_limit  = ?
                               WHERE {name_col} = ?
                               """,
                    (low_limit, name),
                )

    def find_reputation_by_value(self, conn, value):
        cursor = conn.cursor()
        cursor.execute(
            f"""
                       SELECT rep.name, rep.low_limit, rep.high_limit
                       FROM {self.table_name} AS rep
                       WHERE rep.low_limit <= ? AND rep.high_limit >= ?
                       """,
            (value, value),
        )
        result = cursor.fetchone()
        if cursor.rowcount == 0:
            return f"Unknown {self.table_name} for reputation value {value}"
        elif cursor.rowcount > 1:
            return f"Ambiguous {self.table_name} for reputation value {value}"

        return result

    def get_table_name(self):
        return self.table_name
