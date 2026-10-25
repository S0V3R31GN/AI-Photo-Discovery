"""Run local photo ingestion, timing, and isolated workflow verification.

Real photos and derived metadata remain local. The summary contains aggregate
counts/timings/check outcomes only. Controlled correction tests use a temporary
database copy and synthetic annotations; they do not establish model accuracy.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db
import caption
import search
from scripts.export_sample import export_sample

QUERIES = (
    "people gathered at a celebration", "someone wearing blue", "an outdoor activity",
    "a person holding balloons", "a group inside a room",
)


@contextmanager
def isolated_database():
    """Back up the entire SQLite database, including vector tables; remove copy afterward."""
    root = db.REPO_ROOT / "outputs"
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="verification-", dir=root) as folder:
        copy_path = Path(folder) / "verification.db"
        with db.connect() as source:
            destination = sqlite3.connect(copy_path)
            try:
                source.backup(destination)
            finally:
                destination.close()
        original_path = db.DB_PATH
        db.DB_PATH = copy_path
        try:
            yield copy_path
        finally:
            db.DB_PATH = original_path


def digest(record):
    return sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def probe(database, photo_id, expected):
    db.DB_PATH = Path(database)
    return 0 if digest(db.get_photo(photo_id)) == expected else 1


def check(name, passed, report):
    report["checks"][name] = "PASS" if passed else "FAIL"
    print(f"{report['checks'][name]}: {name}", flush=True)


def controlled_checks(records, report, detail):
    if len(records) < 2:
        report["checks"]["isolated_workflow"] = "SKIP: requires two ready photos"
        return
    with isolated_database() as copy_path:
        a, b = records[0]["id"], records[1]["id"]
        marker = f"verification-{time.time_ns()}"
        # These annotations are deliberately synthetic and exist ONLY in the copy.
        for photo_id in (a, b):
            record = db.get_photo(photo_id)
            db.save_review(photo_id, {"event_group": marker, "venue": marker,
                           "people": ["person wearing a blue verification jacket"]},
                           "edited", record["revision"])
        check("exact_event_pivot", {row["id"] for row in search.pivot_event(a)} == {b}, report)
        check("exact_venue_pivot", {row["id"] for row in search.pivot_venue(a)} == {b}, report)
        matches = search.pivot_people(a, 0, k=100)
        ids = [row["id"] for row in matches]
        check("participant_pivot_mapping", b in ids and a not in ids and len(ids) == len(set(ids)), report)

        corrections = dict(caption="Verification staff caption", vision_description="Verification staff description",
                           event="verification activity", location="verification setting", people=[], objects=[],
                           user_input=["verification staff note"], event_group=marker, venue=marker)
        before = db.get_photo(a)
        corrected = db.save_review(a, corrections, "edited", before["revision"])
        with db.connect() as connection:
            person_count = connection.execute("SELECT COUNT(*) FROM person_entries WHERE photo_id=?", (a,)).fetchone()[0]
            text = connection.execute("SELECT search_text FROM indexed_photos WHERE photo_id=?", (a,)).fetchone()[0]
        check("deleted_participant_vectors_removed", person_count == 0, report)
        check("corrected_search_text", "verification jacket" not in text and "verification setting" in text, report)
        stale_rejected = False
        try:
            db.save_review(a, {"location": "stale overwrite"}, "edited", before["revision"])
        except db.RevisionConflict:
            stale_rejected = True
        check("stale_save_rejected", stale_rejected, report)

        # Exercise failure persistence and then REAL model retry, without changing archive edits.
        original_describe = caption.describe
        def fail_description(path):
            raise ValueError("Deliberate verification failure")
        caption.describe = fail_description
        try:
            failed = caption.process_pending(limit=1, photo_ids=[a])
        finally:
            caption.describe = original_describe
        after_failure = db.get_photo(a)
        check("failure_recorded_without_losing_fields", failed["failed"] == 1
              and after_failure["processing_status"] == "failed"
              and all(after_failure[key] == value for key, value in corrections.items()), report)
        print("Running one real regeneration on the temporary database copy…", flush=True)
        retried = caption.process_pending(limit=1, photo_ids=[a])
        detail["isolated_retry"] = retried
        regenerated = db.get_photo(a)
        check("real_retry_and_staff_protection", retried["ready"] == 1
              and regenerated["processing_error"] is None
              and all(regenerated[key] == value for key, value in corrections.items()), report)
        # A separate Python process verifies persisted record state, not just session memory.
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                 "--probe-db", str(copy_path), "--probe-id", a,
                                 "--probe-digest", digest(regenerated)],
                                capture_output=True, text=True, timeout=45)
        check("fresh_process_persistence", result.returncode == 0, report)
        if result.returncode:
            report["probe_error"] = "Fresh-process verification failed; inspect the local environment"
        check("review_decision_preserved", regenerated["review_decision"] == corrected["review_decision"]
              and regenerated["reviewed_at"] == corrected["reviewed_at"], report)
    check("archive_reviews_unchanged", all(db.get_photo(row["id"]) == row for row in records), report)


def run(folder, output_dir):
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        raise ValueError("Input folder does not exist; check the exact local folder path")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {"created_at": datetime.now(timezone.utc).isoformat(),
              "runtime": {"python": platform.python_version(), "os": platform.system(),
                          "architecture": platform.machine(), "processor": platform.processor(),
                          "logical_cpus": os.cpu_count()},
              "checks": {}, "limits": ["No human relevance judgments or caption-accuracy assessment",
                  "Pivot/correction tests use synthetic annotations in a temporary database copy",
                  "Search timing includes embedding and SQLite retrieval, but excludes browser rendering",
                  "Fresh-process persistence is a backend check; not an automated browser restart"]}
    report["package_versions"] = {}
    for package in ("torch", "transformers", "sentence-transformers", "sqlite-vec", "streamlit", "pillow-heif"):
        try:
            report["package_versions"][package] = version(package)
        except PackageNotFoundError:
            report["package_versions"][package] = "not installed"
    detail = {"import_errors": [], "processing": [], "queries": []}
    summary_path = output_dir / "verification-summary.json"
    report["status"] = "INCOMPLETE"
    try:
        db.migrate()
        before_count = len(db.list_photos())
        paths = sorted(path for path in folder.rglob("*")
                       if path.is_file() and path.suffix.lower() in db.IMAGE_EXTENSIONS)
        report["matching_files"] = len(paths)
        photo_ids = set()
        for index, path in enumerate(paths, start=1):
            try:
                photo_ids.add(db.register_upload(path.read_bytes(), path.name))
            except Exception as error:
                # Only the private detail file receives filenames and exception messages.
                detail["import_errors"].append({"file": str(path), "error": str(error)})
                print(f"Registration {index}/{len(paths)} failed: {type(error).__name__}", flush=True)
        report["registration"] = {"unique_folder_photos": len(photo_ids),
                                  "new_records": len(db.list_photos()) - before_count,
                                  "failed_files": len(detail["import_errors"])}
        check("folder_registration", bool(photo_ids) and not detail["import_errors"], report)
        pending = [photo_id for photo_id in sorted(photo_ids)
                   if db.get_photo(photo_id)["processing_status"] != "ready"]
        print(f"Registered {len(photo_ids)} unique folder photos; processing {len(pending)} pending/failed records…", flush=True)
        def progress(item):
            detail["processing"].append(item)
            print(f"Processed {len(detail['processing'])}/{len(pending)}: {item['status']} ({item['seconds']}s)", flush=True)
        if pending:
            caption.process_pending(limit=len(pending), photo_ids=pending, progress=progress)
        records = [db.get_photo(photo_id) for photo_id in sorted(photo_ids)]
        ready = [record for record in records if record["processing_status"] == "ready"]
        report["processing"] = {state: sum(record["processing_status"] == state for record in records)
                                for state in ("pending", "ready", "failed")}
        times = [item["seconds"] for item in detail["processing"]]
        report["processing"]["new_attempts"] = len(times)
        report["processing"]["median_seconds"] = statistics.median(times) if times else None
        report["processing"]["max_seconds"] = max(times) if times else None
        report["processing"]["timing_scope"] = "All new attempts, including failures; first attempt may include model loading"
        check("folder_processing", bool(records) and len(ready) == len(records), report)
        export_sample(records, output_dir / "structured-sample.json")
        report["structured_sample_records"] = len(records)
        if ready:
            indexes_valid = True
            with db.connect() as connection:
                for record in ready:
                    expected_text = search.build_search_text(record)
                    if not expected_text:
                        continue
                    indexed = connection.execute(
                        "SELECT search_text FROM indexed_photos WHERE photo_id=?", (record["id"],)
                    ).fetchone()
                    count = connection.execute(
                        "SELECT COUNT(*) FROM person_entries WHERE photo_id=?", (record["id"],)
                    ).fetchone()[0]
                    indexes_valid = indexes_valid and indexed is not None and indexed[0] == expected_text and count == len(record["people"])
            check("folder_records_indexed", indexes_valid, report)
            # Baseline timing only; no relevance claims from unlabelled query results.
            search.semantic_search(QUERIES[0])  # Warm model cache separately from timed searches.
            elapsed = []
            ordered = True
            for query in QUERIES:
                start = time.perf_counter()
                results = search.semantic_search(query)
                milliseconds = (time.perf_counter() - start) * 1000
                elapsed.append(milliseconds)
                distances = [record["distance"] for record in results]
                ordered = ordered and distances == sorted(distances)
                detail["queries"].append({"query": query, "milliseconds": milliseconds,
                    "results": [{"id": row["id"], "distance": row["distance"]} for row in results]})
            report["search"] = {"timed_queries": len(elapsed), "median_ms": round(statistics.median(elapsed), 2),
                                "max_ms": round(max(elapsed), 2), "relevance_evaluation": "NOT ASSESSED"}
            check("ranked_query_execution", ordered, report)
            controlled_checks(ready, report, detail)
        else:
            report["checks"]["retrieval_and_workflow"] = "SKIP: no ready folder photos"
        report["status"] = "PASS" if report["checks"] and all(value == "PASS" for value in report["checks"].values()) else "FAIL_OR_SKIPPED"
    except Exception as error:
        report["status"] = "ERROR"
        report["error_type"] = type(error).__name__
        detail["fatal_error"] = str(error)
        print(f"Verification stopped: {type(error).__name__}. Details saved locally.", flush=True)
    finally:
        summary_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        (output_dir / "verification-private-details.json").write_text(json.dumps(detail, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print("Private structured sample and diagnostic details were saved locally. Share only the aggregate summary.", flush=True)
    return 0 if report["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--out", type=Path, default=db.REPO_ROOT / "outputs")
    parser.add_argument("--probe-db", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--probe-id", help=argparse.SUPPRESS)
    parser.add_argument("--probe-digest", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.probe_db:
        return probe(args.probe_db, args.probe_id, args.probe_digest)
    if args.folder is None:
        parser.error("--folder is required")
    return run(args.folder, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
