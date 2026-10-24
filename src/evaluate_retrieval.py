"""Opt-in real-model developer checks. Not part of offline synthetic tests."""
import argparse
import json
from pathlib import Path
import time

from src.embedding import configuration, DEFAULT_CONFIG, LocalEncoder
from src.ingest import atomic_text, now
from src.retrieval import load_index, search


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--index-dir", type=Path, default=Path("data/index"))
    parser.add_argument("--cases", type=Path, default=Path("evaluation/retrieval_cases.json"))
    parser.add_argument("--report", type=Path, default=Path("evidence/retrieval_20261024/evaluation.json"))
    args = parser.parse_args()
    started = time.perf_counter()
    config = configuration(args.config)
    encoder = LocalEncoder(config)
    index, chunks, manifest = load_index(args.data_dir, args.index_dir, encoder, config)
    results = []
    for case in json.loads(args.cases.read_text(encoding="utf-8")):
        then = time.perf_counter()
        hits = search(case["question"], index, chunks, encoder)
        expected = case["expected_doc_ids"]
        expected_rank = next((h["rank"] for h in hits if h["doc_id"] in expected), None)
        results.append({**case, "expected_first_rank": expected_rank,
                        "hit_at_5": bool(expected_rank) if expected else None,
                        "query_seconds": time.perf_counter() - then, "results": hits})
    # Reload the persisted real FAISS index, not an in-memory reconstruction.
    reloaded, again, _ = load_index(args.data_dir, args.index_dir, encoder, config)
    reload_results = search(results[0]["question"], reloaded, again, encoder)
    reload_equal = reload_results == results[0]["results"]
    judged = [r for r in results if r["expected_doc_ids"]]
    summary = {"judged_questions": len(judged), "hit_at_5_count": sum(r["hit_at_5"] for r in judged),
               "top_1_expected_document_count": sum(r["expected_first_rank"] == 1 for r in judged),
               "reload_results_identical": reload_equal, "documents": manifest["documents"],
               "chunks": len(chunks), "elapsed_seconds": time.perf_counter() - started,
               "note": "Developer-authored small check set, not a blind benchmark or answer correctness measure"}
    atomic_text(args.report, json.dumps({"executed_at": now(), "summary": summary,
                 "signature": manifest["signature"], "results": results}, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary))
    for result in results:
        print(result["case_id"], "expected rank:", result["expected_first_rank"],
              "top1:", result["results"][0]["doc_id"], "score:", round(result["results"][0]["score"], 6))
    return 0 if reload_equal else 1


if __name__ == "__main__":
    raise SystemExit(main())
