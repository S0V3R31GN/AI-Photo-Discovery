"""Shared SQLite access for the photo discovery app."""

from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
from hashlib import sha256
from io import BytesIO
from PIL import Image

import sqlite_vec

from pillow_heif import register_heif_opener

register_heif_opener()

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp",
    ".heic", ".heif", ".avif",
    ".bmp", ".gif", ".tif", ".tiff",
}


REPO_ROOT = Path(__file__).resolve().parent
DB_PATH = REPO_ROOT / "data" / "photos.db"
PHOTO_DIR = REPO_ROOT / "data" / "photos"

LIST_FIELDS = ("people", "objects", "user_input", "staff_fields")


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.enable_load_extension(True)
        try:
            sqlite_vec.load(connection)
        finally:
            connection.enable_load_extension(False)
        yield connection
    finally:
        connection.close()


def migrate():
    """Create the initial schema; safe to run repeatedly."""
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS photos (
                    id TEXT PRIMARY KEY NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    caption TEXT,
                    vision_description TEXT,
                    event TEXT,
                    location TEXT,
                    event_group TEXT,
                    venue TEXT,
                    people TEXT NOT NULL DEFAULT '[]',
                    objects TEXT NOT NULL DEFAULT '[]',
                    user_input TEXT NOT NULL DEFAULT '[]',
                    metadata TEXT,
                    processing_status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (
                            processing_status IN ('pending', 'ready', 'failed')
                        ),
                    processing_error TEXT,
                    review_decision TEXT,
                    reviewed_at TEXT,
                    staff_fields TEXT NOT NULL DEFAULT '[]',
                    revision INTEGER NOT NULL DEFAULT 0
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS photos_event_group
                ON photos(event_group)
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS photos_venue
                ON photos(venue)
            """)


def decode_photo(row):
    if row is None:
        return None
    record = dict(row)
    for field in LIST_FIELDS:
        record[field] = json.loads(record[field])
    return record


def get_photo(photo_id):
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM photos WHERE id = ?", (photo_id,)
        ).fetchone()
    return decode_photo(row)


def list_photos():
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM photos ORDER BY id"
        ).fetchall()
    return [decode_photo(row) for row in rows]



def register_upload(image_bytes, original_name):
    """Validate an image, store a local copy, and register it once."""
    extensions = {
        "JPEG": ".jpg",
        "PNG": ".png",
        "WEBP": ".webp",
        "HEIF": ".heic",
        "AVIF": ".avif",
        "BMP": ".bmp",
        "GIF": ".gif",
        "TIFF": ".tiff",
    }

    with Image.open(BytesIO(image_bytes)) as image:
        image_format = image.format
        image.verify()

    if image_format not in extensions:
        raise ValueError(f"Unsupported image format: {original_name}")

    photo_id = sha256(image_bytes).hexdigest()
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    target = PHOTO_DIR / (photo_id + extensions[image_format])
    stored_path = target.relative_to(REPO_ROOT).as_posix()

    with connect() as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")

            # Never overwrite an existing file with different contents.
            if target.exists():
                if sha256(target.read_bytes()).hexdigest() != photo_id:
                    raise ValueError(f"Stored file is corrupted: {target}")
            else:
                try:
                    with target.open("xb") as output:
                        try:
                            output.write(image_bytes)
                        except BaseException:
                            target.unlink(missing_ok=True)
                            raise
                except FileExistsError:
                    if sha256(target.read_bytes()).hexdigest() != photo_id:
                        raise ValueError(f"Stored file conflict: {target}")

            existing = connection.execute(
                "SELECT path FROM photos WHERE id = ?", (photo_id,)
            ).fetchone()

            if existing is None:
                connection.execute(
                    "INSERT INTO photos(id, path) VALUES (?, ?)",
                    (photo_id, stored_path),
                )

    return photo_id


if __name__ == "__main__":
    migrate()
    print(f"Database ready: {DB_PATH}")
    print(f"Registered photos: {len(list_photos())}")