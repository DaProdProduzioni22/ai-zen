"""Offline regressions for the feed-to-draft handoff."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import moltbook_fetch as fetch


class FetchContractTests(unittest.TestCase):
    def test_published_today_compares_dates_not_zero_padded_strings(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            article_path = Path(tmp) / 'articles.json'
            article_path.write_text(json.dumps([{'id':'existing', 'published':'9 Ottobre 2026'}]), encoding='utf-8')
            with patch.object(fetch, 'ARTICLES', str(article_path)), patch.object(fetch, 'today_it', return_value='09 Ottobre 2026'):
                self.assertEqual(fetch.published_today(), ['existing'])

    def test_pending_handoff_requests_original_summary_not_unlicensed_copy(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            pending_path = Path(tmp) / 'pending.json'
            post = {'id':'293af133-1400-4564-83f0-9e2993f01b25', 'content':'A useful argument. ' * 23,
                    'author':{'name':'source'}, 'title':'Source title', 'created_at':'2026-10-28T01:32:00Z'}
            with patch.object(fetch, 'PENDING', str(pending_path)), patch.object(fetch, 'published_today', return_value=[]), \
                 patch.object(fetch, 'published_ids', return_value=set()), patch.object(fetch, 'fetch_hot', return_value=[post]), \
                 contextlib.redirect_stdout(io.StringIO()):
                fetch.cmd_next()
            pending = json.loads(pending_path.read_text(encoding='utf-8'))
            self.assertIn("contentType='summary'", pending['note'])
            self.assertIn('reusePermission', pending['note'])
            self.assertNotIn('real EN->IT translation', pending['note'])
            self.assertEqual(pending['content'], post['content'])


if __name__ == '__main__':
    unittest.main()
