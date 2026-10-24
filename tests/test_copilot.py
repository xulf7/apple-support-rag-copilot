"""Synthetic service/HTTP tests. Providers and vectors here are test doubles only."""
import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock, patch

import numpy as np

from src.generation import GenerationSettings
from src.service import RagService, InvalidQuestion, ResourcesUnavailable, select_context, ROOT
from src.ingest import main as ingest_cli, validate_topic
from src.retrieval import build_index, load_index
from src.web import create_app
from test_retrieval import TestEncoder, TestIndex, TestBackend

QUESTION = "How do I cancel an Apple subscription on my iPhone?"


class Provider:
    def __init__(self, output=None, error=None):
        self.output = output if output is not None else {"suggested_response": "Synthetic test suggestion [E2].", "citation_ids": ["E2"]}
        self.error, self.calls = error, []

    def generate(self, request, *, timeout_seconds):
        self.calls.append((request, timeout_seconds))
        if self.error:
            raise self.error
        return self.output


class CopilotTests(unittest.TestCase):
    def setUp(self):
        self.services = []
        self.encoder = TestEncoder()
        self.encoder.encode = Mock(wraps=self.encoder.encode)
        self.settings = json.loads((ROOT / "config/copilot.json").read_text())
        self.chunks = []
        for i, (start, end, doc) in enumerate([(0, 80, "orbit-manual"), (100, 400, "orbit-manual"), (0, 75, "orbit-manual"), (0, 100, "battery-manual")]):
            self.chunks.append({"chunk_id": f"synthetic-{i}", "doc_id": doc, "title": f"Synthetic {doc}",
                                "source_url": f"https://support.apple.com/en-us/{777901 if doc == 'orbit-manual' else 777902}", "heading": "Specific steps" if i == 1 else "Introduction",
                                "content_sha256": f"synthetic-{doc}-version", "start_char": start, "end_char": end,
                                "text": "Synthetic numbered instructions for tests." if i == 1 else "Synthetic introductory explanation.",
                                "context_text": "Synthetic prerequisite."})
        self.index = TestIndex(2)
        scores = np.array([.8, .79, .78, .7], dtype=np.float32)
        self.index.add(np.column_stack([scores, np.sqrt(1 - scores ** 2)]))

    def tearDown(self):
        for service in self.services:
            service.close()

    def service(self, provider=None, timeout=20):
        service = RagService(self.encoder, self.index, self.chunks, {"documents": len({c['doc_id'] for c in self.chunks}), "signature": "synthetic"}, self.settings,
                             GenerationSettings(timeout_seconds=timeout), provider)
        self.services.append(service)
        return service

    def test_later_specific_steps_are_sent_and_cited_not_just_top_one(self):
        provider = Provider()
        result = self.service(provider).ask(QUESTION)
        self.assertEqual(result["status"], "generated")
        request, timeout = provider.calls[0]
        self.assertEqual(len(request["evidence"]), 3)
        self.assertEqual(request["evidence"][1]["heading"], "Specific steps")
        self.assertIn("untrusted", request["instructions"])
        self.assertEqual(timeout, 20)
        self.assertEqual(result["sources"][0]["chunk_id"], "synthetic-1")
        self.assertEqual(result["sources"][0]["source_url"], "https://support.apple.com/en-us/777901")
        self.assertEqual(result["sources"][0]["content_sha256"], "synthetic-orbit-manual-version")
        self.assertEqual((result["sources"][0]["start_char"], result["sources"][0]["end_char"]), (100, 400))
        self.assertEqual(len(result["sources"]), 1)  # candidates and context are not all actual citations

    def test_bad_provider_responses_are_rejected_without_losing_evidence(self):
        outputs = [
            {"suggested_response": "Test [E999]", "citation_ids": ["E999"]},
            {"suggested_response": " ", "citation_ids": []},
            {"suggested_response": "Test [E1]", "citation_ids": ["E1", "E1"]},
            {"suggested_response": "Test [E1]", "citation_ids": ["E1"], "source_url": "https://fake.test"},
            {"suggested_response": "Test [E999]", "citation_ids": ["E1"]},
            {"suggested_response": "Test [E1]", "citation_ids": []},
            {"suggested_response": "Test", "citation_ids": ["E1"]},
            {"suggested_response": "Test [E1]", "citation_ids": ["E1", "E2"]},
            {"suggested_response": "Use https://fake.test [E1]", "citation_ids": ["E1"]},
            {"suggested_response": "x" * 8001, "citation_ids": []},
            {"suggested_response": "Valid prose", "citation_ids": "E1"},
            {"suggested_response": "Valid prose", "citation_ids": [[]]},
            "not json", [], {"suggested_response": "Missing required field"},
        ]
        for output in outputs:
            with self.subTest(output=output):
                result = self.service(Provider(output)).ask(QUESTION)
                self.assertEqual(result["status"], "generation_failed")
                self.assertIsNone(result["answer"])
                self.assertEqual(result["sources"], [])
                self.assertEqual(len(result["evidence"]), 4)

    def test_upstream_exception_is_redacted_and_not_retried(self):
        provider = Provider(error=RuntimeError("PRIVATE_TOKEN absolute-machine-path and upstream payload"))
        client = create_app({"TESTING": True}, service=self.service(provider)).test_client()
        reply = client.post("/api/chat", json={"question": QUESTION})
        self.assertEqual(reply.status_code, 502)
        result = reply.json
        self.assertEqual(result["error"]["code"], "upstream_error")
        self.assertNotIn("PRIVATE_TOKEN", json.dumps(result))
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(sum(h["used_for_generation"] for h in result["evidence"]), 3)

    def test_busy_web_request_has_no_submitted_context_and_worker_recovers(self):
        started, release = Event(), Event()

        class BlockingProvider(Provider):
            def generate(self, request, *, timeout_seconds):
                self.calls.append((request, timeout_seconds))
                started.set()
                release.wait(3)
                return self.output

        provider = BlockingProvider()
        service = self.service(provider, timeout=.02)
        client = create_app({"TESTING": True}, service=service).test_client()
        try:
            first = client.post("/api/chat", json={"question": QUESTION})
            self.assertTrue(started.wait(1))
            second = client.post("/api/chat", json={"question": "How do I cancel a trial?"})
            self.assertEqual((first.status_code, second.status_code), (504, 503))
            self.assertEqual(first.json["error"]["code"], "generation_timeout")
            self.assertEqual(second.json["error"]["code"], "generation_busy")
            sent = [h for h in first.json["evidence"] if h["used_for_generation"]]
            self.assertEqual([h["citation_id"] for h in sent], ["E1", "E2", "E3"])
            self.assertTrue(all(not h["used_for_generation"] and h["citation_id"] is None for h in second.json["evidence"]))
            self.assertEqual(len(provider.calls), 1)
            self.assertEqual(provider.calls[0][0]["question"], QUESTION)
            self.assertEqual(first.json["sources"], second.json["sources"])
        finally:
            release.set()
            service.runner.future.result(timeout=1)
        third = client.post("/api/chat", json={"question": QUESTION})
        self.assertEqual(third.json["status"], "generated")
        self.assertEqual(len(provider.calls), 2)

    def test_valid_prose_and_empty_citations_are_preserved_through_http(self):
        examples = [
            ("  Synthetic normal suggestion [E2].\n", ["E2"]),
            ("The provided evidence does not establish a repair price. Confirm with staff.", []),
            ("Please confirm the device and software version before proceeding.", []),
            ("If the prerequisite holds, follow the supplied procedure [E1].\nOtherwise confirm the device. The evidence does not cover pricing.", ["E1"]),
        ]
        for text, ids in examples:
            with self.subTest(text=text):
                provider = Provider({"suggested_response": text, "citation_ids": ids})
                if ids == ["E2"]:
                    provider.output = json.dumps(provider.output)  # serialized JSON, preserving whitespace
                service = self.service(provider)
                reply = create_app({"TESTING": True}, service=service).test_client().post("/api/chat", json={"question": QUESTION})
                self.assertEqual(reply.status_code, 200)
                self.assertEqual(reply.json["status"], "generated")
                self.assertEqual(reply.json["answer"], text)
                self.assertEqual([s["citation_id"] for s in reply.json["sources"]], ids)
                self.assertTrue(reply.json["review_required"])
                self.assertEqual(len(provider.calls), 1)

    def test_unconfigured_never_infers_semantic_status_from_question(self):
        service = self.service()
        for question in ["How do I request a refund for an iPhone app?",
                         "What is the repair price for a cracked MacBook display?",
                         "Recover permanently deleted photos", "Help with my account",
                         "Set up a telescope before a costly repair.",
                         "What is the oxygen demand of this aquatic ecosystem?"]:
            with self.subTest(question=question):
                result = service.ask(question)
                self.assertEqual(result["status"], "generation_not_configured")
                self.assertIsNone(result["answer"])
                self.assertIsNone(result["reason"])
                self.assertEqual(result["sources"], [])
                self.assertEqual(len(result["evidence"]), 4)
                self.assertTrue(all(not h["used_for_generation"] and h["citation_id"] is None for h in result["evidence"]))

    def test_new_topics_and_multiple_documents_use_dynamic_citation_bindings(self):
        provider = Provider({"suggested_response": "Synthetic protocol response [E1] [E3].",
                             "citation_ids": ["E1", "E3"]})
        result = self.service(provider).ask("Combine the orbital setup and battery-care prerequisites.")
        self.assertEqual(result["status"], "generated")
        self.assertEqual({h["doc_id"] for h in result["sources"]}, {"orbit-manual", "battery-manual"})
        self.assertEqual([h["chunk_id"] for h in result["sources"]], ["synthetic-0", "synthetic-3"])
        self.assertEqual(len(provider.calls), 1)
        submitted = [h for h in result["evidence"] if h["used_for_generation"]]
        self.assertEqual(len(submitted), 3)  # overlapping same-document duplicate excluded
        self.assertEqual(len(result["sources"]), 2)
        self.assertEqual(len(result["evidence"]), 4)
        for source in result["sources"]:
            candidate = next(h for h in result["evidence"] if h["chunk_id"] == source["chunk_id"])
            for key in source:
                self.assertEqual(source[key], candidate[key])

    def test_background_words_do_not_block_submission_to_injected_provider(self):
        provider = Provider()
        service = self.service(provider)
        for question in ["How do I request a refund for an iPhone app?",
                         "Align a telescope before repair; what maintenance steps cost nothing?",
                         "How do I replace this sensor after paying a hardware repair fee?"]:
            self.assertEqual(service.ask(question)["status"], "generated")
        self.assertEqual(len(provider.calls), 3)  # fixture responses, NOT semantic verification
        self.assertTrue(all(len(request["evidence"]) == 3 for request, _ in provider.calls))

    def test_low_scores_are_not_a_semantic_gate(self):
        scores = np.array([.01, -.1, -.2, -.3], dtype=np.float32)
        self.index = TestIndex(2)
        self.index.add(np.column_stack([scores, np.sqrt(1 - scores ** 2)]))
        provider = Provider({"suggested_response": "The supplied evidence does not cover this procedure.", "citation_ids": []})
        self.assertEqual(self.service().ask("Explain this unfamiliar procedure.")["status"], "generation_not_configured")
        result = self.service(provider).ask("Explain this unfamiliar procedure.")
        self.assertEqual(result["status"], "generated")  # prose is shown without semantic classification
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(len(provider.calls[0][0]["evidence"]), 3)
        self.assertTrue(result["evidence"])

    def test_empty_candidates_and_context_budget_are_engineering_outcomes(self):
        self.assertEqual([h["chunk_id"] for h in select_context(self.chunks, self.settings)],
                         ["synthetic-0", "synthetic-1", "synthetic-3"])
        provider = Provider()
        service = self.service(provider)
        service.settings = {**self.settings, "context_char_budget": 20}
        result = service.ask(QUESTION)
        self.assertEqual((result["status"], result["reason"]), ("context_unavailable", "context_budget_exceeded"))
        self.assertFalse(provider.calls)
        self.assertTrue(result["evidence"])
        # No provider: even a small budget cannot become a semantic refusal.
        unconfigured = self.service()
        unconfigured.settings = service.settings
        self.assertEqual(unconfigured.ask(QUESTION)["status"], "generation_not_configured")
        self.chunks = []
        self.index = TestIndex(2)
        empty = self.service(provider).ask(QUESTION)
        self.assertEqual((empty["status"], empty["reason"]), ("no_evidence", "no_candidates"))
        self.assertFalse(provider.calls)

    def test_import_rebuild_reload_new_topics_and_replaced_ids_need_no_service_changes(self):
        # Explicitly synthetic bodies, vectors and persistence backend; no network/model.
        # Two wholly different corpora use the same import/build/load/service code.
        scenarios = [
            [("777901", "telescope_alignment"), ("777902", "battery_care")],
            [("888901", "orchid_cultivation"), ("888902", "water_filtration")],
        ]

        class CiteDocuments(Provider):
            def generate(self, request, *, timeout_seconds):
                self.calls.append((request, timeout_seconds))
                ids = [request["evidence"][0]["citation_id"], request["evidence"][-1]["citation_id"]]
                return {"suggested_response": "Synthetic protocol result. " + " ".join(f"[{cid}]" for cid in ids), "citation_ids": ids}

        for scenario in scenarios:
            with self.subTest(topics=scenario), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                data, index_dir = root / "data", root / "index"
                params = {"max_tokens": 56, "overlap_tokens": 8, "context_tokens": 12}
                encoder = TestEncoder()
                for number, (article, topic) in enumerate(scenario):
                    title = f"Synthetic {topic}"
                    text = f"# {title}\n\n## Preparation\n\n" + "\n\n".join(
                        f"{step}. Synthetic {topic} instruction with a prerequisite and explanation. "
                        "Keep this invented test condition visible when checking local source mapping."
                        for step in range(1, 6))
                    local = root / f"{article}.txt"
                    local.write_text(text, encoding="utf-8")
                    args = ["src.ingest", "--data-dir", str(data), "import", "--file", str(local),
                            "--url", f"https://support.apple.com/en-us/{article}", "--topic", topic,
                            "--format", "text", "--title", title, "--provenance", "Synthetic fixture only"]
                    with patch("sys.argv", args), redirect_stdout(StringIO()):
                        self.assertEqual(ingest_cli(), 0)
                    build_index(data, index_dir, encoder, params, rebuild=bool(number), backend=TestBackend)
                index, chunks, manifest = load_index(data, index_dir, encoder, params, backend=TestBackend)
                provider = CiteDocuments()
                service = RagService(encoder, index, chunks, manifest, self.settings, GenerationSettings(), provider)
                self.services.append(service)
                result = service.ask("Combine these new reference instructions before a repair.")
                self.assertEqual(result["status"], "generated")
                self.assertEqual({h["doc_id"] for h in result["sources"]},
                                 {f"apple-en-us-{article}" for article, _ in scenario})
                self.assertEqual({h["title"] for h in provider.calls[0][0]["evidence"]},
                                 {f"Synthetic {topic}" for _, topic in scenario})
                for source in result["sources"]:
                    original = next(c for c in chunks if c["chunk_id"] == source["chunk_id"])
                    self.assertEqual(source["content_sha256"], original["content_sha256"])
                    self.assertEqual(source["source_url"], original["source_url"])

    def test_topic_metadata_is_validated_without_a_catalog(self):
        self.assertEqual(validate_topic("an_unseen_topic"), "an_unseen_topic")
        for topic in [None, "", " ", " padded ", "bad\x00label", "x" * 81]:
            with self.subTest(topic=topic), self.assertRaises(ValueError):
                validate_topic(topic)

    def test_invalid_question_rejected_by_core(self):
        service = self.service()
        for question in [None, "", " ", "x" * 2001, "bad\x00input", "word " * 100]:
            with self.assertRaises(InvalidQuestion):
                service.ask(question)

    def test_generation_config_does_not_expose_credentials_or_guess_protocol(self):
        settings = GenerationSettings.from_env({"LLM_PROTOCOL": "not-yet-decided", "LLM_ENDPOINT": "https://example.test", "LLM_MODEL": "test", "LLM_API_KEY": "PRIVATE_TOKEN"})
        self.assertEqual(settings.public_state()["code"], "adapter_pending")
        self.assertNotIn("PRIVATE_TOKEN", str(settings.public_state()) + repr(settings))
        for value in ["nan", "infinity", "bad", "0", "61"]:
            self.assertEqual(GenerationSettings.from_env({"LLM_TIMEOUT_SECONDS": value}).public_state()["code"], "invalid_timeout")
        self.assertEqual(GenerationSettings.from_env({"LLM_MODEL": "only-model"}).public_state()["code"], "incomplete_configuration")

    def test_web_parameter_contract_and_status_codes(self):
        client = create_app({"TESTING": True}, service=self.service()).test_client()
        for body in [None, [], {}, {"question": 123}, {"question": ""}, {"question": QUESTION, "extra": 1}, {"question": "bad\x00input"}]:
            reply = client.post("/api/chat", json=body) if body is not None else client.post("/api/chat", data="{broken", content_type="application/json")
            self.assertEqual(reply.status_code, 400)
            self.assertEqual(reply.json["sources"], [])
        self.assertEqual(client.post("/api/chat", data="plain").status_code, 415)
        self.assertEqual(client.get("/api/chat").status_code, 405)
        self.assertEqual(client.post("/api/chat", data="x" * 17000, content_type="application/json").status_code, 413)
        reply = client.post("/api/chat", json={"question": QUESTION})
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json["status"], "generation_not_configured")
        self.assertEqual(set(reply.json), {"status", "answer", "sources", "evidence", "message", "error", "generation", "index_version", "reason", "review_required"})

    def test_app_loads_resources_once_and_two_web_queries_only_encode_questions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ["data/sources.jsonl", "data/index/manifest.json", "models/all-MiniLM-L6-v2/model_revision.json"]:
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("{}")
            (root / "config").mkdir()
            (root / "config/copilot.json").write_text(json.dumps(self.settings))
            with patch("src.service.configuration", return_value={"model_dir": "models/all-MiniLM-L6-v2"}), \
                    patch("src.service.LocalEncoder", return_value=self.encoder) as encoder_factory, \
                    patch("src.service.load_index", return_value=(self.index, self.chunks, {"documents": 2})) as loader:
                app = create_app({"TESTING": True}, service_factory=lambda: RagService.from_local(root, GenerationSettings()))
                client = app.test_client()
                self.assertEqual(client.post("/api/chat", json={"question": QUESTION}).status_code, 200)
                self.assertEqual(client.post("/api/chat", json={"question": QUESTION}).status_code, 200)
                encoder_factory.assert_called_once(); loader.assert_called_once()
                self.assertEqual(self.encoder.encode.call_count, 2)
                self.assertTrue(all(call.args[0] == [QUESTION] for call in self.encoder.encode.call_args_list))

    def test_missing_resources_have_safe_repair_instructions_and_page_still_loads(self):
        unavailable = ResourcesUnavailable("missing_index", "Local index is missing.", ["python -B -m src.retrieval build"])
        app = create_app({"TESTING": True}, service_factory=Mock(side_effect=unavailable))
        client = app.test_client()
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/api/status").status_code, 503)
        reply = client.post("/api/chat", json={"question": QUESTION})
        self.assertEqual(reply.status_code, 503)
        self.assertIn("python -B -m src.retrieval build", reply.json["repair_commands"])

    def test_unexpected_initialization_or_retrieval_error_does_not_leak_details(self):
        app = create_app({"TESTING": True}, service_factory=Mock(side_effect=RuntimeError("PRIVATE_TOKEN")))
        self.assertNotIn("PRIVATE_TOKEN", app.test_client().get("/api/status").get_data(as_text=True))
        service = self.service(); service.ask = Mock(side_effect=RuntimeError("PRIVATE_TOKEN"))
        reply = create_app({"TESTING": True}, service=service).test_client().post("/api/chat", json={"question": QUESTION})
        self.assertEqual(reply.status_code, 503)
        self.assertNotIn("PRIVATE_TOKEN", reply.get_data(as_text=True))

    def test_page_assets_use_safe_text_rendering_and_csp(self):
        client = create_app({"TESTING": True}, service=self.service()).test_client()
        page = client.get("/")
        self.assertIn("STAFF REVIEW REQUIRED", page.get_data(as_text=True))
        self.assertIn("default-src 'self'", page.headers["Content-Security-Policy"])
        with client.get("/static/copilot.js") as asset:
            script = asset.get_data(as_text=True)
        self.assertNotIn("innerHTML", script)
        self.assertIn("textContent", script)
        self.assertIn('parsed.hostname !== "support.apple.com"', script)
        self.assertNotIn("LLM_API_KEY", page.get_data(as_text=True) + script)

    def test_demo_launcher_disables_reloader_debug_and_implicit_dotenv(self):
        from src.web import main
        with patch("sys.argv", ["src.web", "--port", "5010"]), patch("src.web.create_app") as factory:
            main()
        factory.assert_called_once_with()
        factory.return_value.run.assert_called_once_with(host="127.0.0.1", port=5010, debug=False,
                                                       load_dotenv=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    unittest.main()
