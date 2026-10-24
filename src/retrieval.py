"""Heading-aware chunks, a local FAISS exact index, and evidence-only CLI search."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import uuid

from src.embedding import DEFAULT_CONFIG, LocalEncoder, configuration
from src.ingest import atomic_text, check_record, now, read_jsonl

SCHEMA = 1
CHUNKER = "heading-paragraph-offset-v1"


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def corpus(root):
    rows = sorted(read_jsonl(root / "sources.jsonl"), key=lambda row: row["doc_id"])
    if not rows:
        raise ValueError("Empty corpus: import documents into data/sources.jsonl first")
    ids, hashes = set(), set()
    for row in rows:
        check_record(root, row)
        if row["doc_id"] in ids or row["content_sha256"] in hashes:
            raise ValueError("Duplicate active document identity or body")
        ids.add(row["doc_id"])
        hashes.add(row["content_sha256"])
    mapping = [{key: row[key] for key in ["doc_id", "title", "source_url", "final_url", "topic", "locale"]} for row in rows]
    return rows, {"corpus_sha256": fingerprint([(row["doc_id"], row["content_sha256"]) for row in rows]),
                  "source_mapping_sha256": fingerprint(mapping)}


def sections(text):
    headings = list(re.finditer(r"(?m)^(#{1,6}) (.+)$", text))
    stack = []
    result = []
    if headings and text[:headings[0].start()].strip():
        result.append({"heading": "Introduction", "start": 0, "end": headings[0].start()})
    for i, match in enumerate(headings):
        level, title = len(match[1]), match[2]
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            result.append({"heading": " > ".join(t for level, t in stack if level > 1) or "Introduction",
                           "start": start, "end": end})
    return result


def make_chunks(rows, encoder, params):
    limit, overlap = params["max_tokens"], params["overlap_tokens"]
    if not 0 <= overlap < limit <= encoder.max_length:
        raise ValueError("Invalid token/overlap limit for the actual model")
    chunks = []
    for row in rows:
        text = row["text"]
        for section_number, section in enumerate(sections(text)):
            start, end = section["start"], section["end"]
            lead_end = re.search(r"\n\s*\n", text[start:end])
            lead = text[start:start + lead_end.start()] if lead_end else text[start:end]
            # Repeat a short section prerequisite rather than silently losing it.
            context = lead if not re.match(r"(?:\d+\.|-) ", lead) and encoder.count(lead) <= params["context_tokens"] else ""
            cursor, part = start, 0
            while cursor < end:
                prefix = row["title"] + "\n" + section["heading"] + "\n"
                context_text = context if cursor > start else ""
                if context_text:
                    prefix += context_text + "\n"
                if encoder.count(prefix) >= limit:
                    raise ValueError("Title/heading/context leaves no model space; adjust chunk config")
                remaining = text[cursor:end]
                ends = sorted({b for a, b in encoder.offsets(remaining) if b > 0} | {len(remaining)})
                lo, hi = 0, len(ends)
                while lo < hi:
                    mid = (lo + hi) // 2
                    if encoder.count(prefix + remaining[:ends[mid]]) <= limit:
                        lo = mid + 1
                    else:
                        hi = mid
                if lo == 0:
                    raise ValueError("Cannot fit the next token without truncation")
                cut = ends[lo - 1]
                if cut < len(remaining):
                    # Prefer whole paragraphs/steps, falling back to token offsets.
                    boundaries = [m.start() for m in re.finditer(r"\n\s*\n", remaining[:cut + 1]) if m.start() > 0]
                    if boundaries:
                        cut = boundaries[-1]
                body_end = cursor + cut
                while body_end > cursor and text[body_end - 1].isspace():
                    body_end -= 1
                body = text[cursor:body_end]
                encoded = prefix + body
                count = encoder.count(encoded)
                if not body or count > limit:
                    raise ValueError("Chunk length invariant failed")
                chunks.append({"chunk_id": f"{row['doc_id']}:{row['content_sha256'][:12]}:{section_number:03}:{part:03}:{fingerprint(encoded)[:12]}",
                               "doc_id": row["doc_id"], "title": row["title"], "source_url": row["source_url"],
                               "final_url": row["final_url"], "heading": section["heading"],
                               "content_sha256": row["content_sha256"], "start_char": cursor, "end_char": body_end,
                               "context_text": context_text, "text": body, "embedding_text": encoded,
                               "token_count": count})
                if body_end >= end:
                    break
                offsets = encoder.offsets(body)
                next_start = cursor + offsets[-overlap][0] if overlap and len(offsets) > overlap else body_end
                # Enforce progress even when a small paragraph cannot supply overlap.
                cursor = next_start if cursor < next_start < body_end else body_end
                while cursor < end and text[cursor].isspace():
                    cursor += 1
                part += 1
    if not chunks:
        raise ValueError("No information-bearing chunks")
    return chunks


def signature(binding, encoder, params):
    return {"schema": SCHEMA, "chunker": CHUNKER, **binding, "model": encoder.identity,
            "chunking": {key: params[key] for key in ["max_tokens", "overlap_tokens", "context_tokens"]},
            "backend": "faiss.IndexFlatIP", "score": "inner product of L2-normalized vectors = cosine similarity"}


def checked_vectors(values, dimension):
    import numpy as np
    values = np.asarray(values, dtype=np.float32)
    if values.ndim != 2 or values.shape[1] != dimension or not np.isfinite(values).all():
        raise ValueError("Invalid embedding shape or nonfinite values")
    norms = np.linalg.norm(values, axis=1)
    if not np.allclose(norms, 1, atol=1e-4):
        raise ValueError("Embeddings must be nonzero L2-normalized vectors")
    return np.ascontiguousarray(values)


def faiss_backend():
    import faiss
    return faiss


def artifact(index_dir, relative):
    path = (index_dir / relative).resolve()
    if not path.is_relative_to(index_dir.resolve()) or not path.is_file():
        raise ValueError("Index artifact missing or outside the index directory; rebuild required")
    return path


def load_index(root, index_dir, encoder, params, backend=None):
    rows, binding = corpus(root)
    path = index_dir / "manifest.json"
    if not path.is_file():
        raise ValueError("No index manifest; build the index first")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["signature"] != signature(binding, encoder, params):
        raise ValueError("Corpus, source mapping, model or chunk config changed; rebuild required")
    for item in manifest["artifacts"].values():
        file = artifact(index_dir, item["path"])
        if hashlib.sha256(file.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Index artifact hash mismatch; rebuild required")
    chunks = read_jsonl(artifact(index_dir, manifest["artifacts"]["chunks"]["path"]))
    if chunks != make_chunks(rows, encoder, params):
        raise ValueError("Chunk/source mapping mismatch; rebuild required")
    backend = backend or faiss_backend()
    index = backend.read_index(str(artifact(index_dir, manifest["artifacts"]["index"]["path"])))
    if index.ntotal != len(chunks) or index.d != encoder.identity["dimension"] or index.metric_type != backend.METRIC_INNER_PRODUCT:
        raise ValueError("FAISS index dimensions/count/metric mismatch")
    return index, chunks, manifest


def build_index(root, index_dir, encoder, params, rebuild=False, backend=None):
    rows, binding = corpus(root)
    if (index_dir / "manifest.json").exists() and not rebuild:
        index, chunks, manifest = load_index(root, index_dir, encoder, params, backend)
        return {"status": "cached", "documents": len(rows), "chunks": len(chunks), "dimension": index.d}
    chunks = make_chunks(rows, encoder, params)
    vectors = checked_vectors(encoder.encode([chunk["embedding_text"] for chunk in chunks]), encoder.identity["dimension"])
    if len(vectors) != len(chunks):
        raise ValueError("Embedding count mismatch")
    backend = backend or faiss_backend()
    index = backend.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    # Write a new generation; publish manifest last. Existing generations survive.
    generation = index_dir / "generations" / uuid.uuid4().hex
    generation.mkdir(parents=True)
    chunks_path = generation / "chunks.jsonl"
    atomic_text(chunks_path, "".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks))
    index_path = generation / "index.faiss"
    backend.write_index(index, str(index_path))
    manifest = {"created_at": now(), "signature": signature(binding, encoder, params),
                "backend_version": getattr(backend, "__version__", "synthetic-test-double"),
                "documents": len(rows), "chunks": len(chunks), "max_observed_tokens": max(c["token_count"] for c in chunks),
                "artifacts": {key: {"path": file.relative_to(index_dir).as_posix(),
                                     "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
                              for key, file in [("chunks", chunks_path), ("index", index_path)]}}
    atomic_text(index_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return {"status": "built", "documents": len(rows), "chunks": len(chunks), "dimension": index.d,
            "max_observed_tokens": manifest["max_observed_tokens"]}


def search(question, index, chunks, encoder, top_k=5):
    if not isinstance(question, str) or not question.strip() or any(ord(c) < 32 and c not in "\n\t" for c in question):
        raise ValueError("Question must be nonempty text without control characters")
    if not isinstance(top_k, int) or not 1 <= top_k <= 100:
        raise ValueError("top_k must be between 1 and 100")
    if encoder.count(question) > encoder.max_length:
        raise ValueError("Query exceeds the actual model input limit; shorten it")
    vectors = checked_vectors(encoder.encode([question.strip()]), encoder.identity["dimension"])
    scores, indices = index.search(vectors, min(top_k, len(chunks)))
    return [{"rank": rank, "score": float(score), **chunks[int(i)]}
            for rank, (score, i) in enumerate(zip(scores[0], indices[0]), 1) if i >= 0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "query", "inspect"])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--index-dir", type=Path, default=Path("data/index"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--question")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        # Detect empty/invalid data before loading any heavy dependencies.
        corpus(args.data_dir)
        config = configuration(args.config)
        encoder = LocalEncoder(config)
        if args.command == "build":
            result = build_index(args.data_dir, args.index_dir, encoder, config, args.rebuild)
            print(json.dumps({**result, "elapsed_seconds": time.perf_counter() - started}))
        else:
            index, chunks, manifest = load_index(args.data_dir, args.index_dir, encoder, config)
            if args.command == "inspect":
                print(json.dumps(manifest, ensure_ascii=False, indent=2))
            else:
                question = args.question if args.question is not None else input("English question: ")
                results = search(question, index, chunks, encoder, args.top_k)
                if args.json:
                    print(json.dumps({"question": question, "results": results,
                                      "elapsed_seconds": time.perf_counter() - started}, ensure_ascii=False, indent=2))
                else:
                    print("Retrieved evidence only. Cosine similarity is not answer correctness probability.")
                    for result in results:
                        print(f"\n{result['rank']}. score={result['score']:.6f}  {result['chunk_id']}\n"
                              f"Document: {result['doc_id']} | Section: {result['heading']}\n"
                              f"Title: {result['title']}\nSource: {result['source_url']}\n{result['context_text']}\n{result['text']}")
        return 0
    except (ValueError, OSError, KeyError, ImportError) as exc:
        print(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
