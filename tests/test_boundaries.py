"""Regression cases for local text audits and mixed manual-file directories.

Only synthetic content and temporary files are used; no real corpus is required.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.check_corpus import audit
from src.ingest import store

ROOT = Path(__file__).resolve().parents[1]
URL = "https://support.apple.com/en-us/108366"
OTHER = "https://support.apple.com/en-us/101567"
PARAGRAPH = "Synthetic fixture condition and ordered instructions retained for regression checks. " * 9


def html(url, title):
    return (f'<html><head><link rel="canonical" href="{url}"></head>'
            f'<div id="content"><div id="sections"><h1>{title}</h1>'
            f'<p>{PARAGRAPH}</p><h2>Steps</h2><ol><li><p>First step.</p></li>'
            '<li><p>Second step.</p></li></ol></div></div></html>').encode()


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, module, *args):
        return subprocess.run([sys.executable, "-B", "-m", module, *map(str, args)],
                              cwd=ROOT, capture_output=True, encoding="utf-8",
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})

    def text_record(self):
        text = "# Text fixture\n\n## Conditions\n" + PARAGRAPH
        return store(self.root, {"source_url": URL, "topic": "icloud"}, text.encode(),
                     URL, "manual", "Synthetic local fixture", "text", "Text fixture")[1]

    def test_text_integrity_pass_does_not_claim_html_comparison(self):
        row = self.text_record()
        result = audit(self.root, row)
        self.assertTrue(result["passed"])
        self.assertEqual(result["integrity_check"], "passed")
        self.assertEqual(result["html_structure_status"], "not_applicable")
        self.assertNotIn("headings_in_order", result)
        p = self.run_cli("src.check_corpus", "--data-dir", self.root, "--report", self.root / "report.json")
        self.assertEqual(p.returncode, 0, p.stderr)
        summary = json.loads(p.stdout)
        self.assertEqual(summary["html_structural_passed"], 0)
        self.assertEqual(summary["html_structural_not_applicable"], 1)

    def test_bad_text_and_bad_json_do_not_hide_later_html_result(self):
        row = self.text_record()
        (self.root / row["snapshot_path"]).write_bytes(b"corrupted original")
        store(self.root, {"source_url": OTHER, "topic": "apple_account"},
              html(OTHER, "HTML fixture"), OTHER, "manual", "Synthetic local fixture")
        # Put the bad record first, followed by invalid JSON and a good article.
        rows = (self.root / "sources.jsonl").read_text(encoding="utf-8").splitlines()
        bad = next(line for line in rows if json.loads(line)["source_url"] == URL)
        good = next(line for line in rows if json.loads(line)["source_url"] == OTHER)
        (self.root / "sources.jsonl").write_text(bad + '\n{invalid-json\n' + good + '\n', encoding="utf-8")
        p = self.run_cli("src.check_corpus", "--data-dir", self.root, "--report", self.root / "report.json")
        self.assertEqual(p.returncode, 1, p.stderr)
        report = json.loads((self.root / "report.json").read_text())
        self.assertEqual(report["summary"]["failed"], 2)
        self.assertEqual(len(report["results"]), 3)
        self.assertTrue(report["results"][2]["passed"])
        self.assertIn("Snapshot hash mismatch", report["results"][0]["error"])
        self.assertEqual(report["summary"]["html_structural_passed"], 1)

    def test_text_metadata_and_clean_file_still_checked(self):
        row = self.text_record()
        incomplete = dict(row)
        del incomplete["content_sha256"]
        with self.assertRaisesRegex(ValueError, "Incomplete metadata"):
            audit(self.root, incomplete)
        (self.root / row["text_path"]).write_text("corrupted clean text", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Clean text does not match"):
            audit(self.root, row)

    def prepare_manual(self):
        folder = self.root / "manual"
        folder.mkdir()
        seeds = [{"source_url": URL, "topic": "icloud", "observed_title": "First fixture"},
                 {"source_url": OTHER, "topic": "apple_account", "observed_title": "Other fixture"}]
        seed_path = self.root / "seeds.json"
        seed_path.write_text(json.dumps(seeds), encoding="utf-8")
        (folder / "browser name.html").write_bytes(html(URL, "First fixture"))
        (folder / "second.html").write_bytes(html(OTHER, "Other fixture"))
        return folder, seed_path

    def run_import(self, folder, seeds, limit=2):
        p = self.run_cli("src.import_saved", "--manual-dir", folder, "--seeds", seeds,
                         "--data-dir", self.root / "output", "--limit", limit,
                         "--provenance", "Synthetic fixture only", "--report", self.root / "import.json")
        return p, json.loads((self.root / "import.json").read_text(encoding="utf-8"))

    def test_unrelated_and_unrecognized_html_are_reported_not_imported(self):
        folder, seeds = self.prepare_manual()
        (folder / "unrelated.html").write_text("<h1>Unrelated page</h1>")
        (folder / "outside.html").write_bytes(html("https://example.test/page", "Other page"))
        (folder / "not-selected.html").write_bytes(html("https://support.apple.com/en-us/118428", "Not selected"))
        p, report = self.run_import(folder, seeds)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(report["summary"], {"success": 2, "cached": 0, "failed": 0, "skipped": 3})
        self.assertEqual(len(report["skipped_files"]), 3)
        self.assertEqual(len(report["results"]), 2)

    def test_missing_selected_article_fails_while_other_imports(self):
        folder, seeds = self.prepare_manual()
        (folder / "browser name.html").unlink()
        p, report = self.run_import(folder, seeds)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(report["summary"]["success"], 1)
        self.assertIn("No matching", report["results"][0]["reason"])

    def test_duplicate_selected_article_is_not_arbitrarily_chosen(self):
        folder, seeds = self.prepare_manual()
        (folder / "duplicate.html").write_bytes(html(URL, "First fixture"))
        p, report = self.run_import(folder, seeds)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(report["summary"]["success"], 1)
        self.assertIn("Multiple files", report["results"][0]["reason"])
        self.assertFalse(any(row["source_url"] == URL and row["status"] == "success" for row in report["results"]))

    def test_selected_title_mismatch_is_error_and_other_article_continues(self):
        folder, seeds = self.prepare_manual()
        (folder / "browser name.html").write_bytes(html(URL, "Wrong title"))
        p, report = self.run_import(folder, seeds)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(report["summary"]["success"], 1)
        self.assertIn("title does not match", report["results"][0]["reason"])

    def test_recognizable_target_with_missing_canonical_is_error(self):
        folder, seeds = self.prepare_manual()
        (folder / "browser name.html").write_text("<h1>First fixture</h1>")
        p, report = self.run_import(folder, seeds)
        self.assertEqual(p.returncode, 1)
        self.assertIn("No canonical", report["results"][0]["reason"])
        self.assertEqual(report["summary"]["skipped"], 0)

    def test_unselected_article_title_error_does_not_block_selected_pilot(self):
        folder, seeds = self.prepare_manual()
        (folder / "second.html").write_bytes(html(OTHER, "Bad unselected title"))
        p, report = self.run_import(folder, seeds, limit=1)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(report["summary"]["success"], 1)
        self.assertEqual(report["summary"]["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
