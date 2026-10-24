"""Offline synthetic tests. Fixed vectors/backend below are test doubles only.

They do not claim real model or real FAISS validation; those run separately.
"""
import json
from pathlib import Path
import re
import tempfile
import unittest

import numpy as np

from src.ingest import store
from src.retrieval import build_index, corpus, load_index, make_chunks, search


class TestEncoder:
    max_length = 64

    def __init__(self):
        self.identity = {"model_id": "synthetic-test-double", "revision": "test-only", "dimension": 2}
        self.calls = 0

    def count(self, text):
        return len(self.offsets(text)) + 2

    def offsets(self, text):
        return [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]

    def encode(self, texts):
        self.calls += 1
        return np.array([[1.0, 0.0] for text in texts], dtype=np.float32)


class TestIndex:
    metric_type = 0

    def __init__(self, d):
        self.d = d
        self.values = np.empty((0, d), dtype=np.float32)

    @property
    def ntotal(self):
        return len(self.values)

    def add(self, values):
        self.values = np.vstack([self.values, values])

    def search(self, query, k):
        scores = query @ self.values.T
        positions = np.argsort(-scores, kind="stable", axis=1)[:, :k]
        return np.take_along_axis(scores, positions, axis=1), positions


class TestBackend:
    METRIC_INNER_PRODUCT = 0
    IndexFlatIP = TestIndex

    @staticmethod
    def write_index(index, file):
        Path(file).write_text(json.dumps({"d": index.d, "values": index.values.tolist()}))

    @staticmethod
    def read_index(file):
        data = json.loads(Path(file).read_text())
        index = TestIndex(data["d"])
        index.add(np.array(data["values"], dtype=np.float32))
        return index


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data, self.index = self.root / "data", self.root / "index"
        self.encoder = TestEncoder()
        self.params = {"max_tokens": 56, "overlap_tokens": 8, "context_tokens": 12}
        self.text = ("# Synthetic fixture\n\n" + "A local synthetic prerequisite.\n\n" +
                     "## Operation\n\nBefore starting, retain this condition.\n\n" +
                     "\n\n".join(f"{i}. Synthetic step {i} with a condition and an explanation repeated for checking." for i in range(1, 19)))
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        url = "https://support.apple.com/en-us/108366"
        return store(self.data, {"source_url": url, "topic": "icloud"}, self.text.encode(),
                     url, "manual", "Synthetic test fixture only", "text", "Synthetic fixture")[1]

    def build(self, **kwargs):
        return build_index(self.data, self.index, self.encoder, self.params, backend=TestBackend, **kwargs)

    def load(self):
        return load_index(self.data, self.index, self.encoder, self.params, backend=TestBackend)

    def test_deterministic_chunks_stable_ids_and_source_offsets(self):
        rows, _ = corpus(self.data)
        first = make_chunks(rows, self.encoder, self.params)
        self.assertEqual(first, make_chunks(rows, self.encoder, self.params))
        self.assertEqual(len({c["chunk_id"] for c in first}), len(first))
        self.assertGreater(len(first), 2)
        for chunk in first:
            self.assertEqual(chunk["text"], self.text[chunk["start_char"]:chunk["end_char"]])
            self.assertEqual(chunk["source_url"], rows[0]["source_url"])
            self.assertEqual(chunk["content_sha256"], rows[0]["content_sha256"])
            self.assertLessEqual(self.encoder.count(chunk["embedding_text"]), 56)
        self.assertTrue(any(c["context_text"] == "Before starting, retain this condition." for c in first))

    def test_long_paragraph_splits_without_silently_losing_tail(self):
        self.text += "\n\n## Long paragraph\n\n" + " ".join(f"unique{i}" for i in range(200))
        self.save()
        rows, _ = corpus(self.data)
        chunks = make_chunks(rows, self.encoder, self.params)
        joined = " ".join(c["text"] for c in chunks)
        for i in range(200):
            self.assertIn(f"unique{i}", joined)
        self.assertTrue(all(c["token_count"] <= 56 for c in chunks))

    def test_repeat_build_reload_and_explicit_rebuild_never_append(self):
        first = self.build()
        calls = self.encoder.calls
        second = self.build()
        self.assertEqual(second["status"], "cached")
        self.assertEqual(calls, self.encoder.calls)
        a, chunks, _ = self.load()
        results = search("Synthetic question", a, chunks, self.encoder)
        b, reloaded, _ = self.load()
        self.assertEqual(results, search("Synthetic question", b, reloaded, self.encoder))
        rebuilt = self.build(rebuild=True)
        self.assertEqual(first["chunks"], rebuilt["chunks"])
        self.assertEqual(self.load()[0].ntotal, len(chunks))
        self.assertEqual(len(list((self.index / "generations").iterdir())), 2)

    def test_model_or_chunk_config_change_requires_rebuild(self):
        self.build()
        self.encoder.identity["revision"] = "changed"
        with self.assertRaisesRegex(ValueError, "rebuild required"):
            self.load()
        self.encoder.identity["revision"] = "test-only"
        self.params["overlap_tokens"] = 7
        with self.assertRaisesRegex(ValueError, "rebuild required"):
            self.build()

    def test_source_url_mapping_change_requires_rebuild(self):
        self.build()
        path = self.data / "sources.jsonl"
        row = json.loads(path.read_text())
        row["source_url"] += "/"
        path.write_text(json.dumps(row) + "\n")
        with self.assertRaisesRegex(ValueError, "rebuild required"):
            self.load()

    def test_changed_current_body_requires_rebuild(self):
        self.build()
        self.text += "\n\nNew synthetic information."
        self.save()
        with self.assertRaisesRegex(ValueError, "rebuild required"):
            self.load()

    def test_ignores_unreferenced_historical_clean_files(self):
        (self.data / "clean" / "old-version.md").write_text("Do not ingest history")
        result = self.build()
        self.assertEqual(result["documents"], 1)
        self.assertTrue(all("Do not ingest history" not in c["text"] for c in self.load()[1]))

    def test_corrupted_index_artifact_fails_before_loading(self):
        self.build()
        manifest = json.loads((self.index / "manifest.json").read_text())
        path = self.index / manifest["artifacts"]["index"]["path"]
        path.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.load()

    def test_empty_corpus_and_invalid_queries(self):
        with self.assertRaisesRegex(ValueError, "Empty corpus"):
            corpus(self.root / "empty")
        self.build()
        index, chunks, _ = self.load()
        for question in ["", "   ", None, "bad\x00input", "word " * 100]:
            with self.assertRaises(ValueError):
                search(question, index, chunks, self.encoder)
        for k in [0, -1, 101]:
            with self.assertRaises(ValueError):
                search("valid question", index, chunks, self.encoder, k)

    def test_model_limit_includes_title_and_section_prefix(self):
        rows, _ = corpus(self.data)
        for params in [{**self.params, "max_tokens": 100}, {**self.params, "overlap_tokens": 56}]:
            with self.assertRaises(ValueError):
                make_chunks(rows, self.encoder, params)

    def test_valid_text_without_markdown_h1_keeps_preamble(self):
        self.text = self.text.replace("# Synthetic fixture", "Synthetic fixture", 1)
        self.save()
        rows, _ = corpus(self.data)
        chunks = make_chunks(rows, self.encoder, self.params)
        self.assertTrue(any("A local synthetic prerequisite." in c["text"] for c in chunks))


if __name__ == "__main__":
    unittest.main()
