# Apple Support RAG Copilot

MIS2001 academic prototype for internal customer service staff. Suggested responses
will require staff review. This project is not affiliated with Apple.

**Current status: data preparation only.** Six user-saved English (`en-us`) Apple
Support articles passed local integrity and HTML structure checks. Team human
review is still **pending**. Embeddings, indexing, retrieval, LLM generation and
a web interface are **not implemented**; this is not a complete MVP.

The public source tree includes code, synthetic tests, URL seeds and documentation.
It does **not** include Apple article bodies, course handouts, API keys, local
corpus files or raw execution evidence. A fresh checkout starts with no corpus.

## 1. Environment and tests - no corpus needed

Python 3.11.5 was used for local verification. Reuse a suitable existing Python
environment; no automatic environment creation, version switch or upgrade is
required. Runtime dependencies are `requests` and `beautifulsoup4`, declared in
`requirements.txt`. If imports fail, install only the missing dependencies.

From the project root in PowerShell:

```powershell
python -B -m src.check_environment
python -B -m src.ingest --help
python -B -m unittest discover -s tests -v
```

Tests use clearly labelled synthetic fixtures in temporary directories and mocked
network requests. They require no `library/`, real Apple pages, historical evidence
or API key. Test success does not demonstrate real model/API operation.

## 2. Prepare your own local corpus

Article text is third-party material and is not supplied with this source tree.
Obtain pages through permitted public access and observe applicable access/use
conditions. Manual saving does not grant unrestricted redistribution rights.
Do not bypass login, CAPTCHA or access restrictions. Keep saved content local.

1. Select the official URLs in [data/seeds.json](data/seeds.json).
2. Save the first three seed pages (one per topic) from a normal browser as HTML
   into `data/manual/`. Browser-generated filenames are accepted.
3. Import the pilot, inspect raw/clean content, then save/import the remaining pages.

```powershell
New-Item -ItemType Directory -Force -Path data/manual | Out-Null
# Save the first three official pages before running this.
python -B -m src.import_saved --limit 3 --provenance "Describe your actual acquisition method and intended use"
python -B -m src.ingest validate
python -B -m src.check_corpus
# Inspect the pilot, then save the remaining pages before expanding.
python -B -m src.import_saved --limit 6 --provenance "Describe your actual acquisition method and intended use"
```

The importer matches canonical URLs and h1 titles, never renames originals, and
reports skipped unrelated files separately. Missing selected articles, wrong
titles and duplicate selected identities are errors. It never chooses an arbitrary
duplicate. Saved content must still pass extraction and integrity checks.

For UTF-8 text import, retain the exact title, Markdown section headings, ordered
steps and conditions. See the [data contract](docs/DATA_PREPARATION.md) and
[Chinese manual collection guide](docs/MANUAL_COLLECTION_ZH.md).

Automatic HTTP collection remains gated by documented applicable permission and
live robots checks. It is not needed for manual import. Do not invent permission.

## 3. Checks after a corpus exists

```powershell
python -B -m src.ingest validate
python -B -m src.check_corpus
```

Both commands return nonzero for an empty corpus. `validate` checks metadata,
IDs, body/snapshot hashes, local files and deduplication. `check_corpus` also checks
HTML headings, paragraphs, numbered steps and links. Valid text records receive
integrity checks but explicitly report HTML comparison as `not_applicable`; they
are not counted as HTML structure passes. Individual article errors remain in the
report, other articles continue, and errors produce a nonzero exit status.

The only active corpus is `data/sources.jsonl`, which maps each current document
to its raw and clean version. Never ingest every file under `data/clean/`: earlier
versions are retained there. Complete the [human checklist](docs/ARTICLE_REVIEW.md)
before accepting the corpus.

## Public files and local records

- Public: `src/`, `tests/`, `requirements.txt`, `.env.example`, URL-only
  `data/seeds.json`, README and selected documentation under `docs/`.
- Local/ignored: `library/`, `data/manual/`, `data/raw/`, `data/clean/`,
  `data/sources.jsonl`, `data/logs/`, `evidence/`, and the original environment
  report at `docs/ROUND_1_RESULTS.md`. These are absent from a public checkout.
- Generated caches, environments, model/index output, runtime output and review
  packages are also ignored. See [.gitignore](.gitignore).

Read the [task tracker](docs/MVP_PLAN_AND_TASKS.md),
[short data results](docs/MANUAL_IMPORT_RESULTS_20261024.md), and
[public-preparation notes](docs/PUBLIC_PREPARATION.md).

`.env.example` is an empty template for a future generator; this data CLI neither
loads nor needs it. Never publish real keys or personal customer information.
Ignoring files does not untrack existing files or remove them from Git history.
No open-source license has been selected; Apple content is not covered by a
project code license.
