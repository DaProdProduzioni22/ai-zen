"""Daily insertion regression tests. No network or live archive writes."""
import contextlib
import datetime
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("add_article", Path(__file__).with_name("add_article.py"))
assert SPEC is not None and SPEC.loader is not None
add_article = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(add_article)


class DailyArticleTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime.date(2026, 10, 29)
        self.pending = {
            "id": "12345678-1234-1234-1234-123456789abc",
            "created_at": "2026-10-28T09:30:00Z",
            "title_en": "Memory needs a boundary",
            "author": "source_author", "author_karma": 12, "score": 7,
        }
        self.draft = {
            "contentType": "summary",
            "title": "La memoria ha bisogno di un confine",
            "excerpt": "Una sintesi originale sul valore dei limiti.",
            "summary": "La fonte propone di separare i ricordi dalle istruzioni.",
            "content": "<p>The post argues that memory needs a boundary and that agents should check what they retain before using it for a new task.</p>",
            "translation": "<p>Il post propone un confine per la memoria: un agente dovrebbe controllare ciò che conserva prima di usarlo in un nuovo compito.</p>",
            "reflection": "Separare i ricordi dalle istruzioni è una pratica utile.\n\n" + add_article.SIGNATURE,
        }

    def problems(self, articles=None, force=False):
        return add_article.validate(self.draft, self.pending, articles or [], self.today, force)

    def run_cli(self, archive=None, extra=()):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as folder:
            root = Path(folder)
            for name, value in (("draft.json", self.draft), ("pending.json", self.pending),
                                ("articles.json", archive or [])):
                (root / name).write_text(json.dumps(value), encoding="utf-8")
            argv = ["add_article.py", str(root / "draft.json"), "--pending", str(root / "pending.json"),
                    "--today", self.today.isoformat(), *extra]
            output = io.StringIO()
            with patch.object(add_article, "ARTICLES", str(root / "articles.json")), patch("sys.argv", argv):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    result = add_article.main()
            return result, output.getvalue(), json.loads((root / "articles.json").read_text(encoding="utf-8"))

    def test_full_and_legacy_drafts_require_verifiable_permission(self):
        for kind in ("full", None):
            if kind is None:
                self.draft.pop("contentType", None)
            else:
                self.draft["contentType"] = kind
            for permission in (None, "", "   ", "permission granted", True, {"license": "unknown"}):
                with self.subTest(kind=kind, permission=permission):
                    self.draft["reusePermission"] = permission
                    self.assertTrue(any("reusePermission" in p for p in self.problems()), self.problems())

    def test_summary_is_inserted_with_explicit_type_and_source_metadata(self):
        # A summary does not need republication rights. Draft metadata cannot override the source.
        self.draft.update(author="not_the_source", date="invented", published="invented", file="wrong.html")
        result, output, archive = self.run_cli()
        self.assertEqual(result, 0, output)
        entry = archive[0]
        self.assertEqual(entry["contentType"], "summary")
        self.assertEqual(entry["author"], self.pending["author"])
        self.assertEqual(entry["date"], "28 Ottobre 2026")
        self.assertEqual(entry["published"], "29 Ottobre 2026")
        self.assertEqual(entry["postId"], self.pending["id"])
        self.assertEqual(entry["moltbookUrl"], "https://www.moltbook.com/post/" + self.pending["id"])
        self.assertNotIn("reusePermission", entry)

    def test_full_permission_is_preserved_for_explicit_and_legacy_drafts(self):
        for kind in ("full", None):
            with self.subTest(kind=kind):
                if kind is None:
                    self.draft.pop("contentType", None)
                else:
                    self.draft["contentType"] = kind
                self.draft["reusePermission"] = "Autorizzazione a riprodurre e tradurre: https://example.org/permission/123"
                self.assertEqual(self.problems(), [])
                result, output, archive = self.run_cli()
                self.assertEqual(result, 0, output)
                self.assertEqual(archive[0]["contentType"], "full")
                self.assertEqual(archive[0]["reusePermission"], self.draft["reusePermission"])

    def test_invalid_content_type_is_rejected(self):
        for value in ("", "original", None, [], {}):
            with self.subTest(value=value):
                self.draft["contentType"] = value
                self.assertTrue(any("contentType" in p for p in self.problems()))

    def test_same_publication_day_cannot_bypass_rule_with_zero_padding(self):
        self.today = datetime.date(2026, 10, 9)
        self.pending["created_at"] = "2026-10-08T00:00:00Z"
        for published in ("9 Ottobre 2026", "09 Ottobre 2026", "9 ottobre 2026"):
            with self.subTest(published=published):
                articles = [{"id": "already-here", "published": published}]
                self.assertTrue(any("un solo articolo" in p for p in self.problems(articles)))
                self.assertEqual(self.problems(articles, force=True), [])

    def test_invalid_source_dates_are_refused_without_traceback_or_writes(self):
        for value in (None, "", "not-a-date", "2026-02-30T10:00:00Z", "2026-10-28garbage",
                      "2026-10-28T99:00:00Z", 123, "2026-10-30T00:00:00Z"):
            with self.subTest(created_at=value):
                self.pending["created_at"] = value
                result, output, archive = self.run_cli()
                self.assertEqual(result, 1, output)
                self.assertIn("created_at", output)
                self.assertNotIn("Traceback", output)
                self.assertEqual(archive, [])

    def test_invalid_archive_publication_date_fails_closed(self):
        for value in (None, "31 Febbraio 2026", "9 Unknown 2026", 123):
            with self.subTest(published=value):
                archive = [{"id": "old", "published": value}]
                result, output, unchanged = self.run_cli(archive)
                self.assertEqual(result, 1)
                self.assertIn("published", output)
                self.assertEqual(unchanged, archive)

    def test_new_filename_uses_publication_date_without_renaming_archive(self):
        historical = {"id": "historical", "published": "27 Ottobre 2026", "date": "26 Ottobre 2026",
                      "file": "2026-10-26-historical.html", "content": "legacy", "translation": "storico"}
        result, output, archive = self.run_cli([historical])
        self.assertEqual(result, 0, output)
        self.assertTrue(archive[0]["file"].startswith("2026-10-29-"))
        self.assertEqual(archive[1], historical)
        self.assertNotIn("contentType", archive[1])
        self.assertEqual(archive[0]["note"], "Curato il 29 Ottobre 2026 · post del 28 Ottobre 2026")

    def test_dry_run_leaves_archive_unchanged(self):
        result, output, archive = self.run_cli(extra=("--dry-run",))
        self.assertEqual(result, 0, output)
        self.assertEqual(archive, [])

    def test_force_does_not_bypass_duplicate_post_or_permission(self):
        article = {"id": "duplicate", "published": "28 Ottobre 2026", "postId": self.pending["id"]}
        self.assertTrue(any("duplicato" in p for p in self.problems([article], force=True)))
        self.draft["contentType"] = "full"
        self.assertTrue(any("reusePermission" in p for p in self.problems(force=True)))

    def test_valid_iso_source_variants_keep_the_source_calendar_date(self):
        for value in ("2026-10-28", "2026-10-28T23:30:00-04:00", "2026-10-28T09:30:00.123456+00:00"):
            with self.subTest(created_at=value):
                self.pending["created_at"] = value
                result, output, archive = self.run_cli()
                self.assertEqual(result, 0, output)
                self.assertEqual(archive[0]["date"], "28 Ottobre 2026")
        self.pending["created_at"] = "2026-10-29T00:00:00Z"
        result, output, archive = self.run_cli()
        self.assertEqual(result, 0, output)
        self.assertNotIn("note", archive[0])

    def test_summary_cannot_wrap_a_full_copy_of_the_source(self):
        self.pending["content"] = "The post argues that memory needs a boundary and that agents should check what they retain before using it for a new task."
        self.assertTrue(any("sintesi" in p for p in self.problems()))
        self.draft["content"] = "<p>Editorial introduction.</p>" + self.draft["content"]
        self.assertTrue(any("sintesi" in p for p in self.problems()))


if __name__ == "__main__":
    unittest.main()
