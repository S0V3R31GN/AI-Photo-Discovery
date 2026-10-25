"""Exercise the local verification runner without private photos or model downloads."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import db
import caption
import search
from scripts import verify_workflow
from test_pipeline import test_embeddings


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.folder = self.root / "input"
        self.folder.mkdir()
        self.output = self.root / "outputs"
        for i, color in enumerate(("red", "blue")):
            Image.new("RGB", (8, 8), color).save(self.folder / f"private-photo-{i}.png")
        self.patches = [patch.object(db, "REPO_ROOT", self.root),
            patch.object(db, "DB_PATH", self.root / "data/photos.db"),
            patch.object(db, "PHOTO_DIR", self.root / "data/photos"),
            patch.object(search, "embed", test_embeddings),
            patch.object(caption, "describe", return_value="Private generated description"),
            patch.object(caption, "metadata", return_value=dict(event="celebration", location="park",
                        people=["person wearing red"], objects=["balloons"])),
            patch.object(caption, "rich_caption", return_value="Private generated caption")]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def run_verification(self):
        with redirect_stdout(StringIO()):
            result = verify_workflow.run(self.folder, self.output)
        return result, json.loads((self.output / "verification-summary.json").read_text())

    def test_full_run_preserves_archive_and_aggregate_privacy(self):
        code, report = self.run_verification()
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["registration"]["unique_folder_photos"], 2)
        self.assertEqual(report["search"]["relevance_evaluation"], "NOT ASSESSED")
        self.assertEqual(report["checks"]["fresh_process_persistence"], "PASS")
        for record in db.list_photos():
            self.assertEqual(record["staff_fields"], [])
            self.assertIsNone(record["event_group"])
            self.assertEqual(record["caption"], "Private generated caption")
            self.assertNotIn(record["id"], json.dumps(report))
        text = json.dumps(report)
        for private in ("private-photo", "Private generated", "person wearing red", str(self.root)):
            self.assertNotIn(private, text)
        sample = json.loads((self.output / "structured-sample.json").read_text())
        self.assertEqual(len(sample), 2)
        self.assertEqual(sample[0]["people"], ["person wearing red"])
        self.assertEqual(list(self.output.glob("verification-*/*.db")), [])

    def test_repeat_run_does_not_recaption_ready_archive_photos(self):
        self.run_verification()
        code, report = self.run_verification()
        self.assertEqual(code, 0)
        self.assertEqual(report["registration"]["new_records"], 0)
        self.assertEqual(report["processing"]["new_attempts"], 0)
        self.assertIsNone(report["processing"]["median_seconds"])
        self.assertEqual(len(db.list_photos()), 2)

    def test_corrupt_file_is_reported_without_leaking_filename_to_summary(self):
        (self.folder / "private-corrupt.jpg").write_bytes(b"not an image")
        code, report = self.run_verification()
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "FAIL_OR_SKIPPED")
        self.assertEqual(report["registration"]["failed_files"], 1)
        self.assertNotIn("private-corrupt", json.dumps(report))
        private = json.loads((self.output / "verification-private-details.json").read_text())
        self.assertIn("private-corrupt", private["import_errors"][0]["file"])

    def test_empty_folder_does_not_report_success(self):
        for path in self.folder.iterdir():
            path.unlink()
        code, report = self.run_verification()
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "FAIL_OR_SKIPPED")
        self.assertEqual(report["checks"]["folder_registration"], "FAIL")

    def test_exception_writes_aggregate_report_and_keeps_raw_error_local(self):
        with patch.object(verify_workflow, "controlled_checks", side_effect=RuntimeError("private diagnostic")):
            code, report = self.run_verification()
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "ERROR")
        self.assertEqual(report["error_type"], "RuntimeError")
        self.assertNotIn("private diagnostic", json.dumps(report))
        private = json.loads((self.output / "verification-private-details.json").read_text())
        self.assertEqual(private["fatal_error"], "private diagnostic")


if __name__ == "__main__":
    unittest.main()
