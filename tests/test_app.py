"""Streamlit workflow checks with synthetic data and mocked embeddings."""
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from streamlit.testing.v1 import AppTest
import db
import search
from test_pipeline import test_embeddings


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(db, 'REPO_ROOT', root), patch.object(db, 'DB_PATH', root/'data/photos.db'),
                        patch.object(db, 'PHOTO_DIR', root/'data/photos'), patch.object(search, 'embed', test_embeddings)]
        for item in self.patches:
            item.start()
        db.migrate()
        self.app_path = str(Path(__file__).resolve().parents[1]/'app.py')

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def button(self, app, label):
        return next(button for button in app.button if button.label == label)

    def text(self, app, label):
        return next(field for field in app.text_input if field.label == label)

    def add(self, color):
        data = BytesIO()
        Image.new('RGB', (8, 8), color).save(data, format='PNG')
        photo_id = db.register_upload(data.getvalue(), 'demo.png')
        return db.save_generated(photo_id, dict(caption='Demo photo', vision_description='Blue hat',
            event='celebration', location='park', people=['blue hat'], objects=['balloons']))

    def test_empty_archive_starts(self):
        app = AppTest.from_file(self.app_path).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('0 registered photos' in item.value for item in app.markdown))

    def test_select_save_search_and_fresh_session(self):
        record = self.add('blue')
        app = AppTest.from_file(self.app_path).run()
        self.button(app, 'Select').click().run()
        self.assertEqual(len(app.exception), 0)
        self.text(app, 'Confirmed event group').set_value('Event A')
        next(field for field in app.text_area if field.label.startswith('Participant')).set_value('person in red hat')
        self.button(app, 'Save review').click().run()
        self.assertEqual(len(app.exception), 0)
        saved = db.get_photo(record['id'])
        self.assertEqual(saved['people'], ['person in red hat'])
        self.assertEqual(saved['event_group'], 'Event A')
        fresh = AppTest.from_file(self.app_path).run()
        self.text(fresh, 'Search photos').set_value('red hat').run()
        self.assertEqual(len(fresh.exception), 0)
        self.button(fresh, 'Select').click().run()
        self.assertEqual(self.text(fresh, 'Confirmed event group').value, 'Event A')

    def test_stale_form_reports_conflict(self):
        record = self.add('blue')
        app = AppTest.from_file(self.app_path).run()
        self.button(app, 'Select').click().run()
        db.save_review(record['id'], {'location': 'garage'}, 'edited', record['revision'])
        self.text(app, 'Setting').set_value('park')
        self.button(app, 'Save review').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('Review not saved' in error.value for error in app.error))
        self.assertEqual(db.get_photo(record['id'])['location'], 'garage')

    def test_event_pivot(self):
        a, b = self.add('blue'), self.add('red')
        for row in (a, b):
            db.save_review(row['id'], {'event_group': 'Event A'}, 'edited', row['revision'])
        app = AppTest.from_file(self.app_path).run()
        self.button(app, 'Select').click().run()
        self.button(app, 'Same confirmed event').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(sum(button.label == 'Select' for button in app.button), 1)


if __name__ == '__main__':
    unittest.main()
