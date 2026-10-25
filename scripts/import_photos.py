"""Import a folder into the shared photo database."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db


def import_photos(folder):
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        raise ValueError(f"Photo folder does not exist: {folder}")

    db.migrate()
    before = len(db.list_photos())
    processed = failed = 0

    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in db.IMAGE_EXTENSIONS:
            continue

        try:
            db.register_upload(path.read_bytes(), path.name)
            processed += 1
        except Exception as error:
            failed += 1
            print(f"FAILED: {path.name}: {error}")

    after = len(db.list_photos())
    print(f"Added: {after - before}; total records: {after}")
    print(f"Valid files processed: {processed}; failed: {failed}")
    return failed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    sys.exit(1 if import_photos(args.folder) else 0)