"""Rebuild both local vector indexes, preserving photo records and staff edits."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db
import search

if __name__ == "__main__":
    db.migrate()
    print(f"Indexed {search.rebuild_index()} photos")
