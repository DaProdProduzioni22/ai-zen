"""Date-contract regressions: run without writing generated site files."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
from unittest import mock
import unittest
import xml.etree.ElementTree as ET

import build


class DateContractTests(unittest.TestCase):
    def test_real_calendar_day_is_primary_in_static_article_and_archive(self):
        with open(build.ARTICLES, encoding="utf-8") as source:
            articles = json.load(source)
        article = next(a for a in articles if a["id"] == "a-gzip-member-boundary-is-not-the-end-of-a-tool-result")
        before = copy.deepcopy(article)
        expected = 'Su AI Zen: <time datetime="2026-10-27">27 Ottobre 2026</time>'
        original = 'Post originale: <time datetime="2026-10-25">25 Ottobre 2026</time>'
        page = build.render_article_page(article, None, None)
        archive = build.render_blog_index([article])
        for output in (page, archive):
            self.assertIn(expected, output)
            self.assertIn(original, output)
            self.assertLess(output.index(expected), output.index(original))
            self.assertIn(article["file"], output)
        self.assertIn('data-day="2026-10-27"', archive)
        self.assertEqual(before, article)


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.articles = [
            {"id": "new", "slug": "new", "title": "Nuovo", "date": "2 Dicembre 2026", "published": "1 Gennaio 2027", "file": "2026-12-02-new.html", "author": "Fonte"},
            {"id": "fallback", "slug": "fallback", "title": "Fallback", "date": "31 Dicembre 2026", "author": "Fonte"},
            {"id": "old", "slug": "old", "title": "Vecchio", "date": "30 Dicembre 2026", "published": "30 Dicembre 2026", "author": "Fonte"},
        ]
        self.original = copy.deepcopy(self.articles)

    def test_editorial_order_wins_even_when_source_order_is_reversed(self):
        ordered = sorted(self.articles, key=build.sort_key, reverse=True)
        self.assertEqual([a["id"] for a in ordered], ["new", "fallback", "old"])
        self.assertEqual(build.slug_filename(ordered[0]), "2026-12-02-new.html")
        self.assertEqual(build.slug_filename(ordered[1]), "2026-12-31-fallback.html")
        self.assertEqual(self.articles, self.original)

    def test_archive_calendar_and_month_data_use_editorial_date_with_fallback(self):
        archive = build.render_blog_index(self.articles)
        self.assertIn('data-day="2027-01-01" data-month="Gennaio 2027"', archive)
        self.assertIn('data-day="2026-12-31" data-month="Dicembre 2026"', archive)
        self.assertIn('Su AI Zen: <time datetime="2026-12-31">31 Dicembre 2026</time>', archive)

    def test_rss_and_json_use_editorial_dates_without_mutating_original_dates(self):
        root = ET.fromstring(build.render_feed(self.articles))
        channel = root.find("channel")
        assert channel is not None
        self.assertEqual(channel.findtext("lastBuildDate"), build.rfc822("1 Gennaio 2027"))
        items = channel.findall("item")
        self.assertEqual([item.findtext("pubDate") for item in items], [build.rfc822("1 Gennaio 2027"), build.rfc822("31 Dicembre 2026"), build.rfc822("30 Dicembre 2026")])
        self.assertTrue((items[0].findtext("guid") or "").endswith("/2026-12-02-new.html"))
        feed = build.render_api_feed(self.articles)
        self.assertTrue(feed["lastUpdated"].startswith("2027-01-01T"))
        self.assertEqual(feed["generated"], feed["lastUpdated"])
        self.assertEqual(feed["posts"][0]["date"], "2 Dicembre 2026")
        self.assertEqual(feed["posts"][0]["published"], "1 Gennaio 2027")
        self.assertEqual(feed["posts"][0]["publicationDate"], "2027-01-01")
        self.assertEqual(feed["posts"][1]["publicationDate"], "2026-12-31")
        self.assertEqual(feed, build.render_api_feed(self.articles))
        self.assertEqual(self.articles, self.original)

    def test_sitemap_and_related_dates_follow_ai_zen(self):
        sitemap = build.render_sitemap(self.articles)
        self.assertIn('<lastmod>2027-01-01</lastmod>', sitemap)
        page = build.render_article_page(self.articles[1], self.articles[2], self.articles[0], [self.articles[0]])
        self.assertIn('Su AI Zen: <time datetime="2027-01-01">1 Gennaio 2027</time>', page)
        self.assertIn('href="2026-12-02-new.html" rel="next"', page)


class SummaryContentTests(unittest.TestCase):
    def test_summary_is_labelled_as_babbasone_summary_not_source_full_text(self):
        article = {"id": "summary", "slug": "summary", "title": "Sintesi", "date": "25 Ottobre 2026", "published": "27 Ottobre 2026", "author": "AutoreFonte", "contentType": "summary", "content": "<p>English summary.</p>", "translation": "<p>Sintesi italiana.</p>"}
        page = build.render_article_page(article, None, None)
        self.assertTrue('Sintesi EN' in page)
        self.assertTrue('Sintesi IT' in page)
        self.assertIn('<h2>🇮🇹 Sintesi IT</h2>', page)
        self.assertIn('<h2>🇬🇧 Sintesi EN</h2>', page)
        self.assertNotIn('{{IT_HEADING}}', page)
        self.assertNotIn('{{EN_HEADING}}', page)
        self.assertTrue('Sintesi originale di Babbasone, basata sul post di AutoreFonte, non traduzione integrale' in page)
        self.assertFalse('The original' in page)
        self.assertFalse('Ascolta la traduzione italiana' in page)
        self.assertEqual(build.render_api_feed([article])["posts"][0]["contentType"], "summary")
        del article["contentType"]
        legacy = build.render_article_page(article, None, None)
        self.assertTrue('Originale' in legacy)
        self.assertTrue('Ascolta la traduzione italiana' in legacy)
        self.assertFalse('Sintesi originale di Babbasone' in legacy)


class IsolatedBuildTests(unittest.TestCase):
    def test_real_build_is_coherent_and_idempotent_without_touching_repo_outputs(self):
        source_repo = Path(build.REPO)
        with tempfile.TemporaryDirectory(prefix="ai-zen-dates-", dir=os.environ.get("TMPDIR")) as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            (root / "api").mkdir()
            for name in ("index.html", "assets/zen-ui.css", "assets/zen-ui.js", "api/moltbook.json"):
                shutil.copyfile(source_repo / name, root / name)
            targets = (str(root / "index.html"), str(root / "assets/zen-ui.css"))
            with mock.patch.multiple(build, REPO=str(root), BLOG_DIR=str(root / "blog"), API_DIR=str(root / "api"), MOLTBOOK=str(root / "api/moltbook.json"), ILLU_CSS_TARGETS=targets):
                articles, changed = build.build()
                self.assertTrue(changed)
                self.assertEqual(len(list((root / "blog").glob("*.html"))), len(articles) + 1)
                archive = (root / "blog/index.html").read_text(encoding="utf-8")
                api = json.loads((root / "api/feed.json").read_text(encoding="utf-8"))
                rss = ET.parse(root / "feed.xml").getroot().findall("channel/item")
                self.assertEqual(len(rss), len(articles))
                self.assertEqual([post["id"] for post in api["posts"]], [article["id"] for article in articles])
                for article, post, item in zip(articles, api["posts"], rss):
                    effective = build.publication_date(article)
                    self.assertEqual(post["publicationDate"], build.date_iso(effective))
                    self.assertEqual(item.findtext("pubDate"), build.rfc822(effective))
                    self.assertEqual(post["date"], article["date"])
                    self.assertTrue(post["url"].endswith("/" + article["file"]))
                    page = (root / "blog" / article["file"]).read_text(encoding="utf-8")
                    self.assertTrue(build.publication_html(article) in page)
                    self.assertTrue(build.source_date_html(article) in page)
                    self.assertTrue(build.publication_html(article) in archive)
                _, second_changes = build.build()
                self.assertEqual(second_changes, [], "a second build must be byte-identical")


if __name__ == "__main__":
    unittest.main(verbosity=2)
