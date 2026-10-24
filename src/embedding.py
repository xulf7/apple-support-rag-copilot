"""Explicit model download and strictly local CPU sentence encoding.

Importing this module does not import torch or download a model.
"""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

from src.ingest import atomic_text

DEFAULT_CONFIG = Path("config/retrieval.json")


def configuration(path=DEFAULT_CONFIG):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if len(config["revision"]) != 40 or any(c not in "0123456789abcdef" for c in config["revision"]):
        raise ValueError("Model revision must be a pinned 40-character commit")
    for key in ["max_tokens", "batch_size", "cpu_threads", "context_tokens"]:
        if not isinstance(config[key], int) or config[key] < 1:
            raise ValueError(f"Invalid {key}")
    if not 0 <= config["overlap_tokens"] < config["max_tokens"]:
        raise ValueError("overlap_tokens must be nonnegative and below max_tokens")
    return config


def resource_hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()
            and ".cache" not in p.relative_to(folder).parts and p.name != "model_revision.json"}


def download(config):
    from huggingface_hub import snapshot_download
    folder = Path(config["model_dir"])
    snapshot_download(config["model_id"], revision=config["revision"], local_dir=folder,
                      token=False, allow_patterns=["*.json", "*.txt", "*.safetensors"],
                      max_workers=2)
    hashes = resource_hashes(folder)
    if not any(name.endswith(".safetensors") for name in hashes):
        raise ValueError("No safetensors weights downloaded")
    atomic_text(folder / "model_revision.json", json.dumps({"model_id": config["model_id"],
                "revision": config["revision"], "files": hashes}, indent=2) + "\n")
    return {"model_id": config["model_id"], "revision": config["revision"], "files": len(hashes)}


class LocalEncoder:
    def __init__(self, config):
        folder = Path(config["model_dir"])
        marker = folder / "model_revision.json"
        if not marker.is_file():
            raise ValueError("Local model missing; run python -m src.embedding download first")
        recorded = json.loads(marker.read_text(encoding="utf-8"))
        if recorded["model_id"] != config["model_id"] or recorded["revision"] != config["revision"]:
            raise ValueError("Local model revision differs from configuration")
        hashes = resource_hashes(folder)
        if hashes != recorded["files"]:
            raise ValueError("Local model files changed; restore/download the pinned model")
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(config["cpu_threads"])
        self.model = SentenceTransformer(str(folder.resolve()), device="cpu",
                                          local_files_only=True, trust_remote_code=False)
        self.tokenizer = self.model.tokenizer
        self.max_length = int(self.model.max_seq_length)
        if config["max_tokens"] > self.max_length:
            raise ValueError("Configured chunk limit exceeds actual model input limit")
        self.batch_size = config["batch_size"]
        self.identity = {"model_id": config["model_id"], "revision": config["revision"],
                         "resource_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
                         "dimension": int(self.model.get_sentence_embedding_dimension()),
                         "max_length": self.max_length, "tokenizer": type(self.tokenizer).__name__,
                         "encoding": "symmetric SentenceTransformer.encode; no query/document prompt",
                         "normalized": True, "dtype": "float32", "device": "cpu",
                         "batch_size": self.batch_size, "cpu_threads": config["cpu_threads"],
                         "packages": {n: version(n) for n in ["torch", "transformers", "sentence-transformers", "tokenizers"]}}

    def count(self, text):
        return len(self.tokenizer(text, add_special_tokens=True, truncation=False, verbose=False)["input_ids"])

    def offsets(self, text):
        return self.tokenizer(text, add_special_tokens=False, truncation=False,
                              return_offsets_mapping=True, verbose=False)["offset_mapping"]

    def encode(self, texts):
        if not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError("Encoding requires nonempty text")
        if any(self.count(text) > self.max_length for text in texts):
            raise ValueError("Input exceeds actual model limit; truncation is prohibited")
        return self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["download", "check"])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = configuration(args.config)
    if args.command == "download":
        print(json.dumps(download(config)))
    else:
        import time
        started = time.perf_counter()
        encoder = LocalEncoder(config)
        vectors = encoder.encode(["How can I cancel a subscription?", "How can I back up my iPhone?"])
        print(json.dumps({**encoder.identity, "smoke_shape": list(vectors.shape),
                          "elapsed_seconds": time.perf_counter() - started}))


if __name__ == "__main__":
    main()
