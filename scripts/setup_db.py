from pathlib import Path
import sqlite3

repo_root = Path(__file__).resolve().parent.parent
db_path = repo_root / "data" / "photos.db"

db_path.parent.mkdir(parents=True, exist_ok=True)
connection = sqlite3.connect(db_path) # Opens the database or creates it if it doesn't exist.

# Creates a table inside the database.
connection.execute("""
    CREATE TABLE IF NOT EXISTS PHOTOS (
        id TEXT PRIMARY KEY NOT NULL,
        path TEXT NOT NULL,
        caption TEXT,
        metadata TEXT,
        event_group TEXT,
        venue TEXT
        )
"""
)

connection.commit()
connection.close()