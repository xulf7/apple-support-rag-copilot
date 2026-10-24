"""Synthetic reporting checks; no local model, corpus, network or API required."""
import unittest

from src.evaluate_copilot import inspect_response


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.hit = {"rank": 1, "score": .9, "doc_id": "new-topic-document", "chunk_id": "new-topic-chunk",
                    "title": "Synthetic new topic", "heading": "Synthetic section", "source_url": "https://support.apple.com/en-us/777901",
                    "content_sha256": "synthetic-version", "start_char": 0, "end_char": 30,
                    "text": "Synthetic evidence only.", "context_text": "", "used_for_generation": False, "citation_id": None}
        self.body = {"status": "generation_not_configured", "reason": None, "answer": None, "sources": [], "evidence": [self.hit]}

    def test_retrieval_miss_is_reported_separately_from_valid_unconfigured_state(self):
        row = inspect_response({"expected_doc_ids": ["another-reference"]}, 200, self.body)
        self.assertTrue(row["unconfigured_contract_passed"])
        self.assertFalse(row["retrieval"]["hit_at1"])
        self.assertFalse(row["retrieval"]["hit_at5"])
        self.assertIsNone(row["retrieval"]["first_expected_doc_rank"])
        unlabelled = inspect_response({"expected_doc_ids": []}, 200, self.body)
        self.assertFalse(unlabelled["retrieval"]["labelled"])
        self.assertIsNone(unlabelled["retrieval"]["hit_at1"])

    def test_fake_answer_or_submission_claim_does_not_pass_unconfigured_check(self):
        for body in [{**self.body, "status": "generated", "answer": "Synthetic draft"},
                     {**self.body, "evidence": [{**self.hit, "used_for_generation": True, "citation_id": "E1"}]}]:
            self.assertFalse(inspect_response({}, 200, body)["unconfigured_contract_passed"])
