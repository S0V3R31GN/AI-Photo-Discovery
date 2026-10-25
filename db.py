"""Shared SQLite access for the photo discovery app."""

from contextlib import contextmanager
from datetime import datetime, timezone
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
TEXT_FIELDS = ("caption", "vision_description", "event", "location", "event_group", "venue")
EDITABLE_FIELDS = TEXT_FIELDS + ("people", "objects", "user_input")
GENERATED_FIELDS = ("caption", "vision_description", "event", "location", "people", "objects")


class RevisionConflict(RuntimeError):
    """The record changed; reload before retrying the operation."""


def resolve_stored_path(stored_path):
    path = Path(stored_path)
    return path if path.is_absolute() else REPO_ROOT / path


def validate_fields(fields, allowed=EDITABLE_FIELDS):
    if not isinstance(fields, dict):
        raise ValueError("Fields must be a JSON object")
    unexpected = set(fields) - set(allowed)
    if unexpected:
        raise ValueError(f"Unexpected fields: {sorted(unexpected)}")
    clean = {}
    for field, value in fields.items():
        if field in TEXT_FIELDS:
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{field} must be a string or null")
            clean[field] = value.strip() if isinstance(value, str) else None
        else:
            if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
                raise ValueError(f"{field} must be a list of strings")
            clean[field] = [v.strip() for v in value if v.strip()]
    return clean


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
            columns = {row[1].lower() for row in connection.execute("PRAGMA table_info(photos)")}
            additions = {
                "vision_description": "TEXT", "event": "TEXT", "location": "TEXT",
                "people": "TEXT NOT NULL DEFAULT '[]'",
                "objects": "TEXT NOT NULL DEFAULT '[]'",
                "user_input": "TEXT NOT NULL DEFAULT '[]'",
                "processing_status": "TEXT NOT NULL DEFAULT 'pending'",
                "processing_error": "TEXT", "review_decision": "TEXT", "reviewed_at": "TEXT",
                "staff_fields": "TEXT NOT NULL DEFAULT '[]'",
                "revision": "INTEGER NOT NULL DEFAULT 0",
            }
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(f"ALTER TABLE photos ADD COLUMN {name} {definition}")
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
    with Image.open(BytesIO(image_bytes)) as image:
        image.load()

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


def _commit_record(record, expected_revision, previous):
    # Model inference/encoding must finish BEFORE acquiring a write lock.
    import search
    prepared = search.prepare_photo(record, previous)
    with connect() as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT revision FROM photos WHERE id = ?", (record["id"],)
            ).fetchone()
            if current is None:
                raise KeyError(record["id"])
            if current["revision"] != expected_revision:
                raise RevisionConflict("Photo changed during processing. Reload and retry.")
            names = list(EDITABLE_FIELDS) + [
                "staff_fields", "processing_status", "processing_error",
                "review_decision", "reviewed_at",
            ]
            values = [json.dumps(record[n], ensure_ascii=False) if n in LIST_FIELDS
                      else record[n] for n in names]
            connection.execute(
                "UPDATE photos SET " + ", ".join(f"{n} = ?" for n in names)
                + ", revision = revision + 1 WHERE id = ?",
                (*values, record["id"]),
            )
            search.refresh_photo(connection, record, prepared)
            updated = decode_photo(connection.execute(
                "SELECT * FROM photos WHERE id = ?", (record["id"],)
            ).fetchone())
    return updated


def save_generated(photo_id, validated_proposal, expected_revision=None):
    proposal = validate_fields(validated_proposal, GENERATED_FIELDS)
    if set(proposal) != set(GENERATED_FIELDS):
        raise ValueError(f"Generated output requires: {', '.join(GENERATED_FIELDS)}")
    for field in ("caption", "vision_description"):
        if not proposal[field]:
            raise ValueError(f"Generated {field} cannot be empty")
    record = get_photo(photo_id)
    if record is None:
        raise KeyError(photo_id)
    revision = record["revision"]
    if expected_revision is not None and revision != expected_revision:
        raise RevisionConflict("Photo changed during inference. Retry using the latest record.")
    previous = dict(record)
    for field, value in proposal.items():
        if field not in record["staff_fields"]:
            record[field] = value
    record["processing_status"] = "ready"
    record["processing_error"] = None
    return _commit_record(record, revision, previous)


def save_review(photo_id, fields, decision, expected_revision):
    fields = validate_fields(fields)
    if decision not in {"accepted", "edited", "rejected"}:
        raise ValueError("Decision must be accepted, edited, or rejected")
    record = get_photo(photo_id)
    if record is None:
        raise KeyError(photo_id)
    if record["revision"] != expected_revision:
        raise RevisionConflict("Photo changed. Reload before saving.")
    previous = dict(record)
    record.update(fields)
    # Explicitly submitted empty values are protected too.
    record["staff_fields"] = sorted(set(record["staff_fields"]) | set(fields))
    record["review_decision"] = decision
    record["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    return _commit_record(record, expected_revision, previous)


def mark_failed(photo_id, error, expected_revision):
    with connect() as connection:
        with connection:
            changed = connection.execute(
                "UPDATE photos SET processing_status = 'failed', processing_error = ?, "
                "revision = revision + 1 WHERE id = ? AND revision = ?",
                (str(error)[:2000], photo_id, expected_revision),
            ).rowcount
            if not changed:
                raise RevisionConflict("Photo changed; failure status was not applied.")


if __name__ == "__main__":
    migrate()
    print(f"Database ready: {DB_PATH}")
    print(f"Registered photos: {len(list_photos())}")
