"""Bounded generation, accurate failure stages, and redacted troubleshooting output."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image
import caption
import db
import search
from test_pipeline import test_embeddings


class CaptionDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(db, "REPO_ROOT", root), patch.object(db, "DB_PATH", root / "data/photos.db"),
                        patch.object(db, "PHOTO_DIR", root / "data/photos"), patch.object(search, "embed", test_embeddings)]
        for item in self.patches:
            item.start()
        db.migrate()
        out = BytesIO()
        Image.new("RGB", (8, 8), "blue").save(out, format="PNG")
        self.photo_id = db.register_upload(out.getvalue(), "test.png")
        self.meta = dict(event="unknown", location="park", people=["blue jacket"], objects=[])

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_metadata_uses_schema_and_bounded_generation(self):
        client = Mock()
        client.generate.return_value = {"response": json.dumps(self.meta), "done_reason": "stop"}
        with patch.object(caption, "get_ollama", return_value=client):
            self.assertEqual(caption.metadata("Blue jacket in park"), self.meta)
        kwargs = client.generate.call_args.kwargs
        self.assertEqual(kwargs["format"], caption.METADATA_SCHEMA)
        self.assertEqual(kwargs["options"]["num_predict"], 512)
        self.assertEqual(kwargs["options"]["num_ctx"], 2048)
        self.assertFalse(kwargs["stream"])

    def test_caption_generation_is_bounded(self):
        client = Mock()
        client.generate.return_value = {"response": "A person wears blue.", "done_reason": "stop"}
        with patch.object(caption, "get_ollama", return_value=client):
            self.assertEqual(caption.rich_caption("blue", self.meta), "A person wears blue.")
        self.assertEqual(client.generate.call_args.kwargs["options"]["num_predict"], 128)

    def test_complete_valid_json_is_accepted_even_if_token_limit_was_hit(self):
        client = Mock()
        client.generate.return_value = {"response": json.dumps(self.meta) + "\n   ", "done_reason": "length"}
        with patch.object(caption, "get_ollama", return_value=client):
            self.assertEqual(caption.metadata("blue"), self.meta)
        self.assertEqual(client.generate.call_count, 1)

    def test_incomplete_metadata_gets_one_compact_retry(self):
        client = Mock()
        client.generate.side_effect = [
            {"response": '{"event": "an unfinished value', "done_reason": "length"},
            {"response": json.dumps(self.meta), "done_reason": "stop"},
        ]
        with patch.object(caption, "get_ollama", return_value=client):
            self.assertEqual(caption.metadata("blue"), self.meta)
        calls = client.generate.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].kwargs["options"]["num_predict"], 512)
        self.assertEqual(calls[1].kwargs["options"]["num_predict"], 1024)
        self.assertNotEqual(calls[0].kwargs["prompt"], calls[1].kwargs["prompt"])

    def test_repeated_incomplete_metadata_is_never_saved(self):
        client = Mock()
        client.generate.return_value = {"response": '{"people": ["blue', "done_reason": "length"}
        with patch.object(caption, "get_ollama", return_value=client), patch.object(caption, "describe", return_value="blue"), patch.object(caption, "rich_caption") as rich:
            result = caption.process_pending(limit=1)
        self.assertEqual(client.generate.call_count, 2)
        self.assertEqual(result["items"][0]["error_type"], "GenerationLimitError")
        self.assertEqual(result["items"][0]["stage"], "metadata")
        self.assertIsNone(db.get_photo(self.photo_id)["caption"])
        self.assertEqual(db.get_photo(self.photo_id)["people"], [])
        rich.assert_not_called()

    def test_wrong_types_get_one_retry_and_remain_subject_to_validation(self):
        client = Mock()
        client.generate.side_effect = [
            {"response": json.dumps({**self.meta, "people": "blue"}), "done_reason": "stop"},
            {"response": json.dumps(self.meta), "done_reason": "stop"},
        ]
        with patch.object(caption, "get_ollama", return_value=client):
            self.assertEqual(caption.metadata("blue"), self.meta)
        self.assertEqual(client.generate.call_count, 2)

    def test_trailing_non_json_is_not_accepted_as_a_complete_object(self):
        client = Mock()
        client.generate.return_value = {"response": json.dumps(self.meta) + " unfinished text", "done_reason": "length"}
        with patch.object(caption, "get_ollama", return_value=client):
            with self.assertRaises(caption.GenerationLimitError):
                caption.metadata("blue")
        self.assertEqual(client.generate.call_count, 2)

    def test_transport_timeout_is_not_automatically_repeated(self):
        client = Mock()
        client.generate.side_effect = TimeoutError("response timeout")
        with patch.object(caption, "get_ollama", return_value=client):
            with self.assertRaises(TimeoutError):
                caption.metadata("blue")
        self.assertEqual(client.generate.call_count, 1)

    def test_token_limit_rejects_caption(self):
        client = Mock()
        client.generate.return_value = {"response": "A partial caption", "done_reason": "length"}
        with patch.object(caption, "get_ollama", return_value=client):
            with self.assertRaises(caption.GenerationLimitError):
                caption.rich_caption("blue", self.meta)

    def test_success_reports_all_stages(self):
        stages = []
        with patch.object(caption, "describe", return_value="blue"), patch.object(caption, "metadata", return_value=self.meta), patch.object(caption, "rich_caption", return_value="Blue jacket."):
            result = caption.process_pending(limit=1, stage_progress=stages.append)
        item = result["items"][0]
        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["stage"], "complete")
        self.assertIsNone(item["error_type"])
        self.assertEqual(stages, ["verify_image", "vision", "metadata", "caption", "embed_and_save"])
        self.assertEqual(set(item["stage_seconds"]), set(stages))

    def test_failure_stage_tracks_the_actual_operation(self):
        for operation, stage in [("describe", "vision"), ("metadata", "metadata"), ("rich_caption", "caption")]:
            with self.subTest(operation=operation):
                with patch.object(caption, "describe", return_value="blue"), patch.object(caption, "metadata", return_value=self.meta), patch.object(caption, "rich_caption", return_value="Blue jacket."):
                    with patch.object(caption, operation, side_effect=TimeoutError("private response detail")):
                        result = caption.process_pending(limit=1, retry_failed=True)
                item = result["items"][0]
                self.assertEqual(item["stage"], stage)
                self.assertEqual(item["error_type"], "TimeoutError")
                self.assertIn(stage, item["stage_seconds"])
                self.assertIn(f"stage={stage}", db.get_photo(self.photo_id)["processing_error"])
                self.assertIsNone(db.get_photo(self.photo_id)["caption"])
                safe = json.dumps(caption.diagnostic_result(item))
                self.assertNotIn("private response detail", safe)
                self.assertNotIn(self.photo_id, safe)

    def test_save_failure_is_not_attributed_to_ollama(self):
        with patch.object(caption, "describe", return_value="blue"), patch.object(caption, "metadata", return_value=self.meta), patch.object(caption, "rich_caption", return_value="Blue jacket."), patch.object(db, "save_generated", side_effect=RuntimeError("database problem")):
            result = caption.process_pending(limit=1)
        self.assertEqual(result["items"][0]["stage"], "embed_and_save")
        self.assertEqual(result["items"][0]["error_type"], "RuntimeError")

    def test_missing_image_reports_verification_stage(self):
        db.resolve_stored_path(db.get_photo(self.photo_id)["path"]).unlink()
        with patch.object(caption, "describe") as describe:
            result = caption.process_pending(limit=1)
        self.assertEqual(result["items"][0]["stage"], "verify_image")
        self.assertEqual(result["items"][0]["error_type"], "FileNotFoundError")
        describe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
