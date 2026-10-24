"""Framework-independent, process-local RAG coordination with frozen resources."""
import json
from pathlib import Path
from threading import Lock

from src.embedding import LocalEncoder, configuration
from src.generation import GenerationFailure, GenerationRunner, GenerationSettings, INSTRUCTIONS, validate_output
from src.retrieval import fingerprint, load_index, search

ROOT = Path(__file__).resolve().parents[1]


class InvalidQuestion(ValueError):
    pass


class ResourcesUnavailable(Exception):
    def __init__(self, code, message, commands):
        self.code, self.message, self.commands = code, message, commands
        super().__init__(code)


def response(status, message, *, code=None, evidence=None, answer=None, sources=None,
             generation=None, index_version=None, reason=None):
    return {"status": status, "answer": answer, "sources": sources or [], "evidence": evidence or [],
            "message": message, "error": {"code": code, "message": message} if code else None,
            "generation": generation or {}, "index_version": index_version, "reason": reason,
            "review_required": True}


def select_context(evidence, settings):
    """Pack ranked candidates across documents; no topic or document allowlist.

    Scores establish search order only, not semantic sufficiency. Duplicate
    overlap uses document/version identity and source offsets, never topic names.
    """
    selected, used = [], 2
    if not evidence:
        return selected
    for item in evidence:
        duplicate = any(item["doc_id"] == prev["doc_id"] and
                        item["content_sha256"] == prev["content_sha256"] and
                        max(0, min(item["end_char"], prev["end_char"]) - max(item["start_char"], prev["start_char"])) /
                        max(1, min(item["end_char"] - item["start_char"], prev["end_char"] - prev["start_char"])) > 0.65
                        for prev in selected)
        if duplicate:
            continue
        ref = {key: item[key] for key in ["title", "heading", "text", "context_text"]}
        ref["citation_id"] = f"E{len(selected) + 1}"
        size = len(json.dumps(ref, ensure_ascii=False)) + 2
        if used + size > settings["context_char_budget"]:
            continue
        selected.append(item)
        used += size
        if len(selected) >= settings["max_context_chunks"]:
            break
    return selected


class RagService:
    def __init__(self, encoder, index, chunks, manifest, settings, generation=None, provider=None):
        self.encoder, self.index, self.chunks = encoder, index, chunks
        self.settings, self.generation = settings, generation or GenerationSettings.from_env()
        self.index_version = fingerprint(manifest)
        self.documents = manifest.get("documents", len({c["doc_id"] for c in chunks}))
        self.lock = Lock()
        self.runner = GenerationRunner(provider, self.generation.timeout_seconds) if provider is not None else None

    @classmethod
    def from_local(cls, root=ROOT, generation=None):
        root = Path(root)
        for path, code, message, command in [
            (root / "data/sources.jsonl", "missing_corpus", "No active local corpus.", "python -B -m src.import_saved --help"),
            (root / "models/all-MiniLM-L6-v2/model_revision.json", "missing_model", "Local embedding model is missing.", "python -B -m src.embedding download"),
            (root / "data/index/manifest.json", "missing_index", "Local index is missing.", "python -B -m src.retrieval build"),
        ]:
            if not path.is_file():
                raise ResourcesUnavailable(code, message, [command])
        try:
            config = configuration(root / "config/retrieval.json")
            config["model_dir"] = str(root / config["model_dir"])
            encoder = LocalEncoder(config)
            index, chunks, manifest = load_index(root / "data", root / "data/index", encoder, config)
            settings = json.loads((root / "config/copilot.json").read_text(encoding="utf-8"))
            if (not 1 <= settings["candidate_k"] <= 100
                    or not 1 <= settings["max_context_chunks"] <= settings["candidate_k"]
                    or not 500 <= settings["context_char_budget"] <= 50000
                    or settings["max_question_chars"] != 2000):
                raise ValueError("Invalid context selection limits")
            return cls(encoder, index, chunks, manifest, settings, generation)
        except ImportError:
            raise ResourcesUnavailable("missing_dependencies", "Required backend packages are unavailable.", ["conda activate rag", "python -B -m src.check_environment"]) from None
        except (ValueError, OSError, KeyError, TypeError):
            raise ResourcesUnavailable("invalid_resources", "Resources or configuration failed validation. Restore the reviewed files or explicitly rebuild, then restart.", ["python -B -m src.ingest validate", "python -B -m src.retrieval build --rebuild"]) from None

    def status(self):
        return {"retrieval": "ready", "documents": self.documents, "chunks": len(self.chunks),
                "index_version": self.index_version, "generation": self.generation_state()}

    def generation_state(self):
        if self.runner is not None:
            return {"status": "injected_provider", "code": "explicit_injection",
                    "message": "Explicit provider injection; this does not establish real API validation."}
        return self.generation.public_state()

    def ask(self, question):
        if (not isinstance(question, str) or not question.strip() or len(question) > self.settings["max_question_chars"]
                or any(ord(c) < 32 and c not in "\n\t" for c in question)):
            raise InvalidQuestion("Use a nonempty English question without control characters (up to 2000 characters).")
        if self.encoder.count(question) > self.encoder.max_length:
            raise InvalidQuestion("Question exceeds the embedding input limit; shorten it.")
        with self.lock:
            hits = search(question, self.index, self.chunks, self.encoder, self.settings["candidate_k"])
        evidence = [{key: item[key] for key in ["rank", "score", "chunk_id", "doc_id", "title", "heading", "source_url",
                    "content_sha256", "start_char", "end_char", "text", "context_text"]} for item in hits]
        for item in evidence:
            item.update(citation_id=None, used_for_generation=False)
        generation = self.generation_state()

        def result(status, message, **kwargs):
            return response(status, message, evidence=evidence, generation=generation,
                            index_version=self.index_version, **kwargs)

        if not evidence:
            return result("no_evidence", "The loaded index returned no candidate passages. Check the corpus/index or try another question.",
                          reason="no_candidates")
        if self.runner is None:
            return result("generation_not_configured", generation["message"])
        selected = select_context(evidence, self.settings)
        if not selected:
            return result("context_unavailable", "No candidate fits the configured context budget. Review the evidence or adjust the budget.",
                          reason="context_budget_exceeded")
        references, bindings = [], {}
        for number, item in enumerate(selected, 1):
            citation_id = f"E{number}"
            bindings[citation_id] = item
            references.append({"citation_id": citation_id, **{key: item[key] for key in ["title", "heading", "text", "context_text"]}})

        def submitted():
            for citation_id, item in bindings.items():
                item.update(citation_id=citation_id, used_for_generation=True)

        try:
            output = self.runner.call({"instructions": INSTRUCTIONS, "question": question, "evidence": references},
                                      on_submitted=submitted)
            text, ids = validate_output(output, set(bindings))
            sources = [{key: bindings[cid][key] for key in ["citation_id", "chunk_id", "doc_id", "title", "heading", "source_url",
                        "content_sha256", "start_char", "end_char"]} for cid in ids]
            return result("generated", "Suggested response: staff must verify its claims and limitations against the evidence.", answer=text, sources=sources)
        except GenerationFailure as exc:
            messages = {"generation_timeout": "Generation timed out; retrieved evidence is still available.",
                        "generation_busy": "A previous generation call is still running. Retry later; no new call was queued.",
                        "upstream_error": "Generation service failed. Review the retrieved evidence or retry later.",
                        "invalid_response": "Generation returned an invalid response; no suggested reply is shown.",
                        "invalid_citation": "Generation returned unknown, duplicate or inconsistent citations; verify the evidence manually."}
            return result("generation_failed", messages[exc.code], code=exc.code)

    def close(self):
        if self.runner is not None:
            self.runner.close()
