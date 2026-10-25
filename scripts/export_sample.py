"""Export structured metadata locally; outputs may be confidential and must stay out of Git."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db


def export_sample(records, output):
    fields = ("id", "path", "event", "location", "people", "objects", "event_group",
              "venue", "processing_status", "review_decision")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([{field: row[field] for field in fields} for row in records],
                                 indent=2, ensure_ascii=False), encoding="utf-8")
    return len(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=db.REPO_ROOT / "outputs" / "structured-sample.json")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    db.migrate()
    count = export_sample(db.list_photos()[:args.limit], args.out)
    print(f"Exported {count} records locally. Keep the metadata file confidential.")
