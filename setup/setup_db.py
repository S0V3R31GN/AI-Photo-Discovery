import sqlite3

# Opens the database or creates it if it doesn't exist.
connection = sqlite3.connect("photos.db")

# Creates a table inside the database.
connection.execute("""
    CREATE TABLE IF NOT EXISTS PHOTOS (
        id TEXT PRIMARY KEY,
        path TEXT NOT NULL,
        caption TEXT
        metadata TEXT
        )
"""
)

connection.commit()
connection.close()