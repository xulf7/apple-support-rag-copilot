"""Optional REAL local-model checks; separate from synthetic offline unit tests.

Read-only corpus/index use, generation explicitly unconfigured. Instrumentation
wraps the real encoder/loader: it never replaces vectors or retrieval results.
Outputs local evidence, not an answer-quality metric or a blind evaluation.
"""
import argparse
import json
from pathlib import Path
import time
from unittest.mock import patch

import src.service as service_module
from src.generation import GenerationSettings
from src.service import ROOT, RagService
from src.web import create_app


def inspect_response(case, http_status, body):
    """Report retrieval and no-provider protocol separately; never grade semantics."""
    hits = body.get("evidence", [])
    expected = case.get("expected_doc_ids", [])
    rank = next((h["rank"] for h in hits if h["doc_id"] in expected), None)
    return {"case": case, "http_status": http_status, "status": body["status"],
            "reason": body["reason"], "top_doc": hits[0]["doc_id"] if hits else None,
            "top_score": hits[0]["score"] if hits else None, "evidence_count": len(hits),
            "retrieval": {"labelled": bool(expected), "first_expected_doc_rank": rank,
                          "hit_at1": rank == 1 if expected else None,
                          "hit_at5": rank is not None and rank <= 5 if expected else None},
            "unconfigured_contract_passed": http_status == 200 and bool(hits)
            and body["status"] == "generation_not_configured" and body["reason"] is None
            and body["answer"] is None and body["sources"] == []
            and all(not h["used_for_generation"] and h["citation_id"] is None for h in hits)}


def evaluate(root=ROOT, extra_cases=None):
    root = Path(root)
    cases = json.loads((root / "evaluation/retrieval_cases.json").read_text(encoding="utf-8"))
    cases += json.loads((root / "evaluation/copilot_gaps.json").read_text(encoding="utf-8"))
    if extra_cases is not None:
        cases += json.loads(Path(extra_cases).read_text(encoding="utf-8"))
    started = time.perf_counter()
    with patch.object(service_module, "LocalEncoder", wraps=service_module.LocalEncoder) as constructor, \
            patch.object(service_module, "load_index", wraps=service_module.load_index) as loader:
        app = create_app(service_factory=lambda: RagService.from_local(root, generation=GenerationSettings()))
        service = app.extensions["rag_service"]
        if service is None:
            raise RuntimeError(app.extensions["rag_startup_error"]["code"])
        startup_seconds = time.perf_counter() - started
        encoder_id, index_id = id(service.encoder), id(service.index)
        rows = []
        with patch.object(service.encoder, "encode", wraps=service.encoder.encode) as encode:
            with app.test_client() as client:
                for case in cases:
                    query_started = time.perf_counter()
                    reply = client.post("/api/chat", json={"question": case["question"]})
                    body = reply.get_json()
                    rows.append({**inspect_response(case, reply.status_code, body),
                                 "seconds": time.perf_counter() - query_started})
            lifecycle = {"encoder_initializations": constructor.call_count, "full_index_loads": loader.call_count,
                         "query_encode_calls": encode.call_count,
                         "only_individual_questions_encoded": all(len(c.args[0]) == 1 and c.args[0][0] == case["question"]
                                                                   for c, case in zip(encode.call_args_list, cases)),
                         "objects_reused": id(service.encoder) == encoder_id and id(service.index) == index_id}
        lifecycle_passed = (lifecycle["encoder_initializations"] == lifecycle["full_index_loads"] == 1
                            and lifecycle["query_encode_calls"] == len(cases)
                            and lifecycle["only_individual_questions_encoded"] and lifecycle["objects_reused"])
        result = {"mode": "real local model/index via Flask test client; NO generation provider",
                  "startup_seconds": startup_seconds, "elapsed_seconds": time.perf_counter() - started,
                  "resources": service.status(), "model": service.encoder.identity,
                  "settings": service.settings, "lifecycle": lifecycle, "lifecycle_passed": lifecycle_passed,
                  "retrieval": {"labelled": sum(r["retrieval"]["labelled"] for r in rows),
                                "hit_at1": sum(r["retrieval"]["hit_at1"] is True for r in rows),
                                "hit_at5": sum(r["retrieval"]["hit_at5"] is True for r in rows),
                                "misses": [r["case"]["case_id"] for r in rows if r["retrieval"]["hit_at1"] is False]},
                  "unconfigured_contract": {"passed": sum(r["unconfigured_contract_passed"] for r in rows),
                                            "total": len(rows),
                                            "failures": [r["case"]["case_id"] for r in rows if not r["unconfigured_contract_passed"]]},
                  "semantic_validation": {"status": "pending_real_llm_and_human_review", "executed": False},
                  "cases": rows}
        service.close()
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("evidence/copilot_evaluation_latest.json"))
    parser.add_argument("--extra-cases", type=Path, help="Additional review cases; default keeps the original 21")
    args = parser.parse_args()
    result = evaluate(extra_cases=args.extra_cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ["retrieval", "unconfigured_contract", "semantic_validation", "startup_seconds", "elapsed_seconds", "lifecycle", "lifecycle_passed"]}))
    for row in result["cases"]:
        print(f'{row["case"]["case_id"]}: {row["status"]}, top={row["top_doc"]} score={row["top_score"]}, expected_rank={row["retrieval"]["first_expected_doc_rank"]}, semantics=PENDING')
    return 0 if (not result["retrieval"]["misses"] and not result["unconfigured_contract"]["failures"]
                 and result["lifecycle_passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
