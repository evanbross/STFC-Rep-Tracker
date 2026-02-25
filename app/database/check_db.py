
import sqlite3
import os

db_path = 'stfc_rep_tracker.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

# Check Reputations table info
if ('Reputations',) in tables:
    cursor.execute("PRAGMA table_info(Reputations);")
    columns = cursor.fetchall()
    print("Reputations columns:")
    for col in columns:
        print(col)
else:
    print("Reputations table NOT found!")

conn.close()
