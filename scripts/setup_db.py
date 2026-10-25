"""Create or expand the shared schema without dropping existing records."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db

if __name__ == "__main__":
    db.migrate()
    print(f"Database ready: {db.DB_PATH}")
    print(f"Registered photos: {len(db.list_photos())}")
