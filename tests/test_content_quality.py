"""Synthetic content-boundary regressions; no Apple body/model/network required."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.check_corpus import audit
from src.ingest import check_record, digest, extract_html, read_jsonl
from src.retrieval import build_index, load_index, search
from test_retrieval import TestBackend, TestEncoder


ROOT = Path(__file__).resolve().parents[1]
URL = "https://support.apple.com/en-us/777903"
TITLE = "Synthetic error-message troubleshooting"
TEXT = (f"# {TITLE}\n\n## Before you begin\n\n"
        "Synthetic fixture only. Access Denied and Page Not Found are messages, not a verdict on this article.\n\n"
        + "Keep this synthetic prerequisite and its explanation with the associated procedure. " * 10
        + "\n\n## Need more help?\n\n"
        "1. Choose your device before following the appropriate synthetic instructions.\n\n"
        "2. Confirm the documented prerequisite and preserve the conditional branch.\n")


def html():
    return (f'<html><head><link rel="canonical" href="{URL}"></head>'
            f'<div id="content"><div id="sections"><h1>{TITLE}</h1>'
            '<nav><p>Choose your device</p><p>Synthetic navigation only</p></nav>'
            '<h2>Before you begin</h2><p>Access Denied and Page Not Found are messages discussed by this synthetic guide.</p>'
            '<p>' + "Keep this synthetic prerequisite and its explanation with the associated procedure. " * 10
            + '</p><h2>Need more help?</h2><ol><li>Choose your device before following the appropriate instructions.</li>'
            '<li>Confirm the documented prerequisite and preserve the conditional branch.</li></ol>'
            '<form><p>Synthetic feedback widget only</p></form><footer><p>Synthetic footer only</p></footer>'
            '</div></div></html>')


class ContentQualityTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-B", "-m", "src.ingest", *map(str, args)],
                              cwd=ROOT, capture_output=True, encoding="utf-8",
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})

    def test_error_names_and_device_instruction_pass_cli_audit_build_and_reload(self):
        for fmt, body in [("text", TEXT), ("html", html())]:
            with self.subTest(format=fmt), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                data = root / "data"
                file = root / ("synthetic." + ("txt" if fmt == "text" else "html"))
                file.write_text(body, encoding="utf-8")
                p = self.run_cli("--data-dir", data, "import", "--file", file, "--format", fmt,
                                 "--title", TITLE, "--url", URL, "--topic", "unseen_error_explanations",
                                 "--provenance", "Synthetic regression fixture only")
                self.assertEqual(p.returncode, 0, p.stderr)
                q = self.run_cli("--data-dir", data, "validate")
                self.assertEqual(q.returncode, 0, q.stderr)
                row = read_jsonl(data / "sources.jsonl")[0]
                check_record(data, row)
                result = audit(data, row)
                self.assertTrue(result["passed"], result)
                self.assertEqual(result["html_structure_status"], "passed" if fmt == "html" else "not_applicable")
                for phrase in ["Access Denied", "Page Not Found", "Choose your device", "## Need more help?"]:
                    self.assertIn(phrase, row["text"])
                self.assertNotIn("Synthetic feedback widget", row["text"])
                encoder = TestEncoder()
                params = {"max_tokens": 56, "overlap_tokens": 8, "context_tokens": 12}
                first = build_index(data, root / "index", encoder, params, backend=TestBackend)
                repeat = build_index(data, root / "index", encoder, params, backend=TestBackend)
                self.assertEqual(repeat["status"], "cached")
                index, chunks, manifest = load_index(data, root / "index", encoder, params, backend=TestBackend)
                self.assertEqual(first["chunks"], index.ntotal)
                self.assertEqual(manifest["documents"], 1)
                self.assertTrue(search("Explain Access Denied for my device", index, chunks, encoder))
                self.assertTrue(all(c["doc_id"] == row["doc_id"] and c["content_sha256"] == row["content_sha256"] for c in chunks))

    def test_actual_error_shell_and_navigation_only_body_fail_cli_and_log_failure(self):
        bodies = ["<body>Access Denied</body>", "<main><h1>Page Not Found</h1><p>Sorry.</p></main>",
                  '<main><h1>Navigation shell</h1><nav><h2>Menu</h2><p>' + "Synthetic menu item " * 100 + "</p></nav></main>"]
        for body in bodies:
            with self.subTest(body=body[:35]), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                file = root / "shell.html"
                file.write_text(body, encoding="utf-8")
                p = self.run_cli("--data-dir", root / "data", "import", "--file", file, "--format", "html",
                                 "--url", URL, "--topic", "synthetic", "--provenance", "Synthetic failure fixture")
                self.assertEqual(p.returncode, 1)
                self.assertEqual(read_jsonl(root / "data/sources.jsonl"), [])
                self.assertEqual(read_jsonl(root / "data/logs/events.jsonl")[-1]["status"], "failed")

    def test_extra_structural_pollution_fails_audit_even_with_consistent_hashes(self):
        from src.ingest import store
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            row = store(root, {"source_url": URL, "topic": "synthetic"}, html().encode(),
                        URL, "manual", "Synthetic fixture only")[1]
            self.assertTrue(audit(root, row)["passed"])
            # No error/nav keyword: this is extra text from an actual excluded form.
            row["text"] += "\nSynthetic feedback widget only\n"
            row["content_sha256"] = digest(row["text"])
            (root / row["text_path"]).write_text(row["text"], encoding="utf-8")
            check_record(root, row)
            result = audit(root, row)
            self.assertFalse(result["passed"])
            self.assertFalse(result["body_matches_snapshot"])
            self.assertTrue(result["headings_in_order"])
            self.assertTrue(result["ordered_step_numbers_match"])

    def test_contact_cta_uses_dom_identity_not_heading_wording(self):
        action = '<a link-type="ICON" href="https://getsupport.apple.com/?caller=ikb">Synthetic contact action</a>'
        group = '<div class="gb-group"><h2>Any synthetic CTA heading</h2><p>' + action + '</p></div>'
        cases = [
            (group, True),
            ('<section>' + group + '</section>', False),  # not a direct child of sections
            (group.replace(action, '<span>' + action + '</span>'), False),  # anchor not direct in p
            (group.replace('link-type="ICON"', 'link-type="TEXT"'), False),
            (group.replace('https://getsupport.apple.com/', 'https://getsupport.apple.com.evil.test/'), False),
            (group.replace('</div>', '<ol><li>Retain this substantive step.</li></ol></div>'), False),
        ]
        for extra, removed in cases:
            with self.subTest(extra=extra):
                raw = html().replace('</div></div>', extra + '</div></div>')
                _, text, _ = extract_html(raw, URL)
                self.assertEqual("Synthetic contact action" not in text, removed)
                self.assertIn("## Need more help?", text)

    def test_article_and_main_containers_are_audited_like_section_containers(self):
        from src.ingest import store
        for tag in ["article", "main"]:
            with self.subTest(container=tag), tempfile.TemporaryDirectory() as temp:
                raw = html().replace('<div id="content"><div id="sections">', f'<{tag}>').replace('</div></div>', f'</{tag}>')
                root = Path(temp)
                row = store(root, {"source_url": URL, "topic": "synthetic_new_layout"}, raw.encode(),
                            URL, "manual", "Synthetic layout fixture")[1]
                self.assertTrue(audit(root, row)["passed"])


if __name__ == "__main__":
    unittest.main()
