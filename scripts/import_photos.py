"""
Register local JPG/PNG paths in SQLite without copying image files.

Only Python's standard library is required. Captions and metadata are filled
by later processing; importing again preserves existing rows and corrections.
"""

import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import uuid


REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "photos.db"
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def resolve_stored_path(value):
    """Interpret relative database paths relative to the repo root."""
    path = Path(value)
    return (path if path.is_absolute() else REPO_ROOT / path).resolve()


def stored_path_for(path):
    """Keep repo-local paths portable; use absolute paths for external files."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def import_photos(folder):
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise ValueError(f"Photo folder does not exist: {folder}")
    if not DB_PATH.is_file():
        raise ValueError("Database missing. Run python scripts/setup_db.py first.")

    # mode=rw prevents an incorrect path from silently creating an empty DB.
    with closing(sqlite3.connect(DB_PATH.as_uri() + "?mode=rw", uri=True)) as connection:
        columns = {
            row[1].lower()
            for row in connection.execute("PRAGMA table_info(photos)")
        }
        required = {"id", "path", "caption", "metadata", "event_group", "venue"}
        missing = required - columns
        if missing:
            raise ValueError(
                "Database is missing columns: " + ", ".join(sorted(missing))
                + ". Update the database schema before importing."
            )

        imported = skipped = 0
        # Serialize imports so two concurrent runs cannot insert the same path.
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            known_paths = {
                resolve_stored_path(row[0])
                for row in connection.execute("SELECT path FROM photos")
            }
            for candidate in sorted(folder.rglob("*")):
                if not candidate.is_file():
                    continue
                if candidate.suffix.lower() not in PHOTO_EXTENSIONS:
                    continue
                path = candidate.resolve()
                if path in known_paths:
                    skipped += 1
                    continue

                connection.execute(
                    "INSERT INTO photos (id, path) VALUES (?, ?)",
                    (str(uuid.uuid4()), stored_path_for(path)),
                )
                known_paths.add(path)
                imported += 1

        total = connection.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
    print(f"Imported: {imported}; already registered: {skipped}; total rows: {total}")
    print(f"Database: {DB_PATH}")
    if imported + skipped == 0:
        print("No JPG, JPEG, or PNG files found in that folder or its subfolders.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "folder", type=Path,
        help="Photo folder; relative paths use your terminal's current folder.",
    )
    args = parser.parse_args()
    try:
        import_photos(args.folder)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"Import failed: {error}\n")


if __name__ == "__main__":
    main()
