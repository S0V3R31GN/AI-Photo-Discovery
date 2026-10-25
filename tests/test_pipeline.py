"""Synthetic images and deterministic test embeddings; no private data or model downloads."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
import db
import search
import caption


def test_embeddings(texts):
    # Tests SQLite geometry/integration, NOT the quality of MiniLM embeddings.
    terms = ('blue', 'red', 'balloons', 'car', 'park', 'garage', 'hat', 'staff')
    vectors = []
    for text in texts:
        vector = np.array([1 + text.lower().count(term) * 10 for term in terms], dtype=np.float32)
        vectors.append(vector / np.linalg.norm(vector))
    return np.asarray(vectors)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(db, 'REPO_ROOT', root), patch.object(db, 'DB_PATH', root/'data/photos.db'),
                        patch.object(db, 'PHOTO_DIR', root/'data/photos'), patch.object(search, 'embed', test_embeddings)]
        for item in self.patches:
            item.start()
        db.migrate()
        self.counter = 0

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def photo(self):
        self.counter += 1
        out = BytesIO()
        Image.new('RGB', (8, 8), (self.counter, 30, 70)).save(out, format='PNG')
        return db.register_upload(out.getvalue(), 'photo.png')

    def proposal(self, people=None):
        return dict(caption='Original caption mentions red', vision_description='Original red description',
                    event='celebration', location='park', people=people or ['person wearing red'], objects=['balloons'])

    def generate(self, photo_id, people=None):
        return db.save_generated(photo_id, self.proposal(people))

    def test_registration_and_repeat_migration_preserve_rows(self):
        photo_id = self.photo()
        path = db.resolve_stored_path(db.get_photo(photo_id)['path'])
        self.assertEqual(sha256(path.read_bytes()).hexdigest(), photo_id)
        self.assertEqual(db.register_upload(path.read_bytes(), 'other.png'), photo_id)
        db.migrate()
        self.assertEqual(len(db.list_photos()), 1)
        with self.assertRaises(Exception):
            db.register_upload(b'not an image', 'fake.png')

    def test_generated_validation_is_atomic(self):
        photo_id = self.photo()
        proposal = self.proposal()
        proposal['people'] = 'person in red'
        with self.assertRaises(ValueError):
            db.save_generated(photo_id, proposal)
        self.assertEqual(db.get_photo(photo_id)['revision'], 0)
        self.assertEqual(db.get_photo(photo_id)['processing_status'], 'pending')

    def test_protect_every_edited_field_including_empty_values(self):
        photo_id = self.photo()
        record = self.generate(photo_id)
        corrections = dict(caption='Staff caption', vision_description='', event=None,
                           location='garage', people=[], objects=[], user_input=['staff blue'],
                           event_group='event A', venue='venue A')
        updated = db.save_review(photo_id, corrections, 'edited', record['revision'])
        regenerated = self.generate(photo_id, ['person in blue hat'])
        for key, value in corrections.items():
            self.assertEqual(regenerated[key], value, key)
        self.assertEqual(set(regenerated['staff_fields']), set(corrections))
        self.assertEqual(regenerated['review_decision'], 'edited')
        self.assertEqual(regenerated['reviewed_at'], updated['reviewed_at'])

    def test_text_excludes_prose_and_group_names(self):
        record = db.get_photo(self.photo())
        record.update(self.proposal())
        record['event_group'] = 'secret group'
        record['venue'] = 'secret venue'
        text = search.build_search_text(record)
        self.assertNotIn('Original', text)
        self.assertNotIn('secret', text)
        self.assertIn('People: person wearing red.', text)

    def test_removing_people_deletes_old_participant_vectors(self):
        photo_id = self.photo()
        record = self.generate(photo_id, ['red hat', 'blue coat'])
        db.save_review(photo_id, {'people': []}, 'edited', record['revision'])
        with db.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM person_entries').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM person_vectors').fetchone()[0], 0)
            text = conn.execute('SELECT search_text FROM indexed_photos WHERE photo_id=?', (photo_id,)).fetchone()[0]
        self.assertNotIn('red hat', text)
        self.assertNotIn('blue coat', text)
        self.assertIn('red', db.get_photo(photo_id)['caption'])  # Prose is deliberately excluded from embeddings.

    def test_general_knn_and_person_pivot_deduplicate(self):
        a, b, c = self.photo(), self.photo(), self.photo()
        self.generate(a, ['person wearing blue'])
        self.generate(b, ['person wearing blue', 'person wearing blue hat'])
        self.generate(c, ['person wearing red'])
        self.assertEqual(search.pivot_people(a, 0, k=1)[0]['id'], b)
        ids = [row['id'] for row in search.pivot_people(a, 0)]
        self.assertEqual(set(ids), {b, c})
        self.assertEqual(len(ids), 2)
        self.assertIn(search.semantic_search('blue', k=1)[0]['id'], {a, b})

    def test_group_pivots_require_exact_nonempty_values(self):
        a, b, c = self.photo(), self.photo(), self.photo()
        self.assertEqual(search.pivot_event(a), [])
        for photo_id, group in [(a, 'A'), (b, 'A'), (c, 'a')]:
            db.save_review(photo_id, {'event_group': group, 'venue': 'Hall'}, 'edited', 0)
        self.assertEqual([r['id'] for r in search.pivot_event(a)], [b])
        self.assertEqual({r['id'] for r in search.pivot_venue(a)}, {b, c})

    def test_stale_review_and_generation_are_rejected(self):
        photo_id = self.photo()
        record = self.generate(photo_id)
        db.save_review(photo_id, {'people': ['blue hat']}, 'edited', record['revision'])
        with self.assertRaises(db.RevisionConflict):
            db.save_review(photo_id, {'people': ['red hat']}, 'edited', record['revision'])
        with self.assertRaises(db.RevisionConflict):
            db.save_generated(photo_id, self.proposal(), expected_revision=record['revision'])
        self.assertEqual(db.get_photo(photo_id)['people'], ['blue hat'])

    def test_edit_during_encoding_does_not_get_lost(self):
        photo_id = self.photo()
        record = self.generate(photo_id)
        original = search.prepare_photo
        def concurrent_edit(proposed, previous=None):
            prepared = original(proposed, previous)
            with db.connect() as conn:
                with conn:
                    conn.execute('UPDATE photos SET revision=revision+1 WHERE id=?', (photo_id,))
            return prepared
        with patch.object(search, 'prepare_photo', concurrent_edit):
            with self.assertRaises(db.RevisionConflict):
                db.save_review(photo_id, {'caption': 'stale'}, 'edited', record['revision'])
        self.assertNotEqual(db.get_photo(photo_id)['caption'], 'stale')

    def test_vector_error_rolls_back_photo_and_vectors(self):
        photo_id = self.photo()
        record = self.generate(photo_id)
        original_refresh = search.refresh_photo
        def fail_after_vector_write(*args):
            original_refresh(*args)
            raise RuntimeError('simulated vector failure')
        with patch.object(search, 'refresh_photo', fail_after_vector_write):
            with self.assertRaises(RuntimeError):
                db.save_review(photo_id, {'people': ['blue hat']}, 'edited', record['revision'])
        self.assertEqual(db.get_photo(photo_id), record)
        with db.connect() as conn:
            self.assertEqual(conn.execute('SELECT description FROM person_entries').fetchone()[0], 'person wearing red')

    def test_worker_continues_failure_retry_and_skips_ready(self):
        a, b = self.photo(), self.photo()
        def describe(path):
            if Path(path).stem == a:
                raise ValueError('bad response')
            return 'a blue hat'
        meta = dict(event='unknown', location='unknown', people=['blue hat'], objects=[])
        with patch.object(caption, 'describe', describe), patch.object(caption, 'metadata', return_value=meta), patch.object(caption, 'rich_caption', return_value='Blue hat.'):
            summary = caption.process_pending()
        self.assertEqual((summary['ready'], summary['failed']), (1, 1))
        self.assertIn('bad response', db.get_photo(a)['processing_error'])
        self.assertEqual(db.get_photo(b)['processing_status'], 'ready')
        self.assertEqual(caption.process_pending()['items'], [])
        with patch.object(caption, 'describe', return_value='blue'), patch.object(caption, 'metadata', return_value=meta), patch.object(caption, 'rich_caption', return_value='Blue hat.'):
            retry = caption.process_pending(retry_failed=True)
        self.assertEqual(retry['ready'], 1)
        self.assertIsNone(db.get_photo(a)['processing_error'])
        self.assertEqual(db.get_photo(b)['revision'], 1)

    def test_rebuild_preserves_corrections_and_survives_new_connections(self):
        photo_id = self.photo()
        record = self.generate(photo_id)
        updated = db.save_review(photo_id, {'people': ['blue hat']}, 'edited', record['revision'])
        self.assertEqual(search.rebuild_index(), 1)
        self.assertEqual(db.get_photo(photo_id), updated)
        self.assertEqual(search.semantic_search('blue')[0]['id'], photo_id)
        with db.connect() as conn:
            self.assertEqual(conn.execute('SELECT revision FROM indexed_photos').fetchone()[0], updated['revision'])

    def test_prose_only_review_does_not_run_encoder_or_replace_people(self):
        photo_id = self.photo()
        record = self.generate(photo_id)
        with db.connect() as conn:
            old_id = conn.execute('SELECT id FROM person_entries').fetchone()[0]
        with patch.object(search, 'embed', side_effect=AssertionError('encoder should not run')):
            updated = db.save_review(photo_id, {'caption': 'Staff prose'}, 'accepted', record['revision'])
        self.assertEqual(updated['caption'], 'Staff prose')
        with db.connect() as conn:
            self.assertEqual(conn.execute('SELECT id FROM person_entries').fetchone()[0], old_id)

    def test_malformed_metadata_rejected_and_unknown_retained(self):
        valid = dict(event='unknown', location=None, people=[], objects=[])
        self.assertEqual(caption.validate_metadata(valid), valid)
        for invalid in ({}, {**valid, 'people': [123]}, {**valid, 'event': []}, {**valid, 'venue': 'guess'}):
            with self.assertRaises(ValueError):
                caption.validate_metadata(invalid)

    def test_index_model_mismatch_rolls_back_save(self):
        photo_id = self.photo()
        record = self.generate(photo_id)
        with db.connect() as conn:
            with conn:
                conn.execute("UPDATE search_index_meta SET model_id='other model'")
        with self.assertRaises(RuntimeError):
            db.save_review(photo_id, {'people': ['blue']}, 'edited', record['revision'])
        self.assertEqual(db.get_photo(photo_id), record)
        search.rebuild_index()
        self.assertEqual(search.semantic_search('red')[0]['id'], photo_id)


if __name__ == '__main__':
    unittest.main()
