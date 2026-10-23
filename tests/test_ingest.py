"""Synthetic fixtures only: these tests are NOT real Apple-page validation."""
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch, Mock

import requests
from src.ingest import (Fetcher, collect, extract_html, identity, read_jsonl,
                        store, check_record)
from src.import_saved import discover

URL = "https://support.apple.com/en-us/108366"
SEED = {"source_url": URL, "topic": "icloud"}
PARAGRAPH = ("Synthetic test-only paragraph. Keep this prerequisite and note in the correct section. " * 9)
HTML = (f'<html><nav>Global store navigation</nav><main><h1>Fixture article</h1>'
        f'<p>{PARAGRAPH}</p><h2>Before you begin</h2><p>Important condition.</p>'
        '<h2>Steps</h2><ol start="2"><li>First fixture step<ol><li>Nested step</li></ol></li>'
        '<li>Second fixture step <a href="/en-us/101567">linked evidence</a></li></ol>'
        '<p>Published Date: October 1, 2026</p><h2>Need more help?</h2><p>Get suggestions</p>'
        '<form>Maximum character limit is 250.</form><footer>Legal footer</footer></main></html>').encode()


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, raw=HTML, **kwargs):
        return store(self.root, SEED, raw, URL, "manual", "Synthetic test fixture only", **kwargs)

    def test_extract_structure_links_conditions_and_remove_chrome(self):
        title, text, published = extract_html(HTML.decode(), URL)
        self.assertEqual(title, "Fixture article")
        self.assertEqual(published, "October 1, 2026")
        for fragment in ["## Before you begin", "Important condition", "2. First", "  1. Nested", "3. Second", "https://support.apple.com/en-us/101567"]:
            self.assertIn(fragment, text)
        for fragment in ["Global store", "Legal footer", "Maximum character", "Need more help", "Get suggestions"]:
            self.assertNotIn(fragment, text)

    def test_reject_200_error_or_navigation_page(self):
        for raw in ["<body>Access denied</body>", "<main><h1>Not found</h1><p>Sorry</p></main>",
                    HTML.decode().replace(PARAGRAPH, "Access denied " + PARAGRAPH)]:
            with self.assertRaises(ValueError):
                extract_html(raw, URL)

    def test_saved_apple_sections_and_canonical_mapping(self):
        raw = HTML.decode().replace("<main>", '<div id="content"><div id="sections">').replace("</main>", "</div></div>")
        raw = raw.replace("<html>", f'<html><head><link rel="canonical" href="{URL}"></head>')
        title, text, _ = extract_html(raw, URL)
        self.assertEqual(title, "Fixture article")
        self.assertIn("Important condition.", text)
        self.assertNotIn("Global store", text)
        with self.assertRaisesRegex(ValueError, "canonical URL"):
            extract_html(raw, URL.replace("108366", "118428"))

    def test_standalone_action_link_and_paragraph_boundaries(self):
        raw = HTML.decode().replace('<h2>Steps</h2>', '<a href="https://account.apple.com/">Action link</a><h2>Steps</h2>')
        raw = raw.replace('First fixture step', '<p>First paragraph.</p><p>Second paragraph.</p>')
        _, text, _ = extract_html(raw, URL)
        self.assertIn('[Action link](https://account.apple.com/)', text)
        self.assertIn('2. First paragraph. Second paragraph.', text)

    def test_manual_filename_is_irrelevant_and_duplicate_identity_rejected(self):
        raw = HTML.decode().replace("<html>", f'<html><head><link rel="canonical" href="{URL}"></head>')
        file = self.root / "Any browser filename - Apple Support.html"
        file.write_text(raw, encoding="utf-8")
        seeds = [{**SEED, "observed_title": "Fixture article"}]
        self.assertEqual(discover(self.root, seeds)[0][identity(URL)][0], file)
        (self.root / "another.html").write_text(raw, encoding="utf-8")
        found, skipped, errors = discover(self.root, seeds)
        self.assertNotIn(identity(URL), found)
        self.assertFalse(skipped)
        self.assertIn("Multiple files", errors[identity(URL)][0])

    def test_metadata_artifacts_and_repeat_dedup(self):
        status, row = self.save()
        self.assertEqual(status, "success")
        check_record(self.root, row)
        self.assertEqual(row["human_review"], "pending")
        self.assertEqual(self.save()[0], "cached")
        self.assertEqual(len(read_jsonl(self.root / "sources.jsonl")), 1)
        self.assertEqual((self.root / row["snapshot_path"]).read_bytes(), HTML)

    def test_updated_body_replaces_record_and_preserves_snapshot(self):
        _, old = self.save()
        _, new = self.save(HTML.replace(b"Important condition.", b"Changed condition."))
        self.assertNotEqual(old["content_sha256"], new["content_sha256"])
        self.assertTrue((self.root / old["snapshot_path"]).is_file())
        self.assertEqual(len(read_jsonl(self.root / "sources.jsonl")), 1)

    def test_reject_cross_article_duplicate(self):
        self.save()
        with self.assertRaisesRegex(ValueError, "Identical body"):
            store(self.root, {**SEED, "source_url": URL.replace("108366", "118428")}, HTML,
                  URL.replace("108366", "118428"), "manual", "Test")

    def test_manual_text_import_retains_original_and_null_date(self):
        text = "# Fixture article\n\n## Section\n" + PARAGRAPH
        _, row = self.save(text.encode(), fmt="text", title="Fixture article")
        self.assertIsNone(row["published_at"])
        self.assertEqual(row["ingestion_method"], "manual")
        self.assertTrue(row["snapshot_path"].endswith(".txt"))

    def test_reject_redirect_or_wrong_host_locale(self):
        for url in ["http://support.apple.com/en-us/108366", "https://support.apple.com.evil/en-us/108366", URL + "?key=foo"]:
            with self.assertRaises(ValueError):
                identity(url)
        with self.assertRaisesRegex(ValueError, "Redirect"):
            store(self.root, SEED, HTML, URL.replace("en-us", "en-gb"), "http", "Test")

    def test_corruption_is_not_cache_success(self):
        _, row = self.save()
        (self.root / row["text_path"]).write_text("corrupt", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.save()

    def test_missing_metadata_and_snapshot_rejected(self):
        _, row = self.save()
        bad = dict(row)
        del bad["fetched_at"]
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            check_record(self.root, bad)
        (self.root / row["snapshot_path"]).unlink()
        with self.assertRaisesRegex(ValueError, "Missing artifact"):
            check_record(self.root, row)

    def test_policy_block_and_failure_isolation_no_network(self):
        with patch.object(Fetcher, "get") as get:
            result = collect(self.root, [{"source_url": "https://evil.test", "topic": "icloud"}, SEED])
        get.assert_not_called()
        self.assertEqual(result, {"success": 0, "cached": 0, "blocked": 1, "failed": 1})
        events = read_jsonl(self.root / "logs/events.jsonl")
        self.assertEqual(len(events), 2)
        self.assertFalse((self.root / "sources.jsonl").exists())

    @patch("src.ingest.time.sleep")
    def test_timeout_retry_is_bounded(self, sleep):
        fetcher = Fetcher()
        fetcher.session.get = Mock(side_effect=requests.Timeout())
        with self.assertRaises(requests.Timeout):
            fetcher.get(URL)
        self.assertEqual(fetcher.session.get.call_count, 3)
        self.assertEqual(fetcher.session.get.call_args.kwargs["timeout"], 20)
        self.assertFalse(fetcher.session.get.call_args.kwargs["allow_redirects"])

    @patch("src.ingest.time.sleep")
    def test_access_restrictions_do_not_retry(self, sleep):
        for status in [401, 403, 429]:
            fetcher = Fetcher()
            fetcher.session.get = Mock(return_value=Mock(status_code=status))
            with self.assertRaisesRegex(ValueError, "Access restricted"):
                fetcher.get(URL)
            self.assertEqual(fetcher.session.get.call_count, 1)

    @patch("src.ingest.time.sleep")
    def test_server_failure_then_success(self, sleep):
        fetcher = Fetcher()
        good = Mock(status_code=200, is_redirect=False)
        fetcher.session.get = Mock(side_effect=[Mock(status_code=503, is_redirect=False), good])
        self.assertIs(fetcher.get(URL), good)
        self.assertEqual(fetcher.session.get.call_count, 2)

    def test_robots_denied_with_permission(self):
        grant = self.root / "permission.json"
        grant.write_text(json.dumps({"basis": "Synthetic permission only", "allowed_urls": [URL]}))
        with patch.object(Fetcher, "get", return_value=Mock(text="User-agent: *\nDisallow: /")) as get:
            result = collect(self.root, [SEED], grant)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(result["blocked"], 1)

    def test_cli_manual_import_repeat_and_validate(self):
        local = self.root / "fixture.txt"
        local.write_text("# Fixture article\n\n## Section\n" + PARAGRAPH, encoding="utf-8")
        command = [sys.executable, "-m", "src.ingest", "--data-dir", str(self.root), "import",
                   "--file", str(local), "--format", "text", "--title", "Fixture article",
                   "--url", URL, "--topic", "icloud", "--provenance", "Synthetic test fixture only"]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["status"], "success")
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)["status"], "cached")
        result = subprocess.run([sys.executable, "-m", "src.ingest", "--data-dir", str(self.root), "validate"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["documents"], 1)

    def test_cli_failed_import_logged_and_not_added(self):
        local = self.root / "error.html"
        local.write_text("<main>Access denied</main>")
        result = subprocess.run([sys.executable, "-m", "src.ingest", "--data-dir", str(self.root),
                                 "import", "--file", str(local), "--format", "html", "--url", URL,
                                 "--topic", "icloud", "--permission-basis", "Synthetic test only"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(read_jsonl(self.root / "logs/events.jsonl")[0]["status"], "failed")
        self.assertEqual(read_jsonl(self.root / "sources.jsonl"), [])

    def test_cli_empty_corpus_is_not_success(self):
        result = subprocess.run([sys.executable, "-m", "src.ingest", "--data-dir", str(self.root), "validate"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["structural_checks"], "empty_corpus")


if __name__ == "__main__":
    unittest.main()
