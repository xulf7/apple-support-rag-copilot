# Data preparation and acceptance

## Access and provenance

Review date: 2026-10-23, Asia/Shanghai. The provided materials require allowed
public access and prohibit circumvention.

Apple's [Website Terms of Use](https://www.apple.com/legal/internet-services/terms/site.html)
include restrictions in “Your Use of the Site” on page scraping/robots and
conditions on copying knowledge-base material in “Content”. On that basis,
automatic article collection is blocked by default. This is an implementation
decision based on the observed terms, not a claim of legal permission or a legal
opinion. Ordinary page visibility and robots allowance do not resolve reuse
permission. Do not publish imported full text or treat manual copying as a way
around these restrictions.

The [robots file](https://support.apple.com/robots.txt), viewed through the web
tool, has a wildcard group whose disallow patterns do not match these six direct
article URLs. Local requests for robots failed: sandbox ProxyError/WinError
10061; approved out-of-sandbox retry SSLError/UNEXPECTED_EOF_WHILE_READING.
TLS verification was never disabled; no proxy, headers, or browser identities
were changed to circumvent restrictions. Metadata verification through the web
tool is not a raw snapshot or successful local HTTP ingestion.

For automated collection, first obtain and record an actual applicable permission
basis (including permitted copying/cleaning/storage). A JSON file outside source
control must contain `basis` describing that evidence and `allowed_urls` listing
only covered article URLs. No permission record has been supplied or invented.
The CLI accepts `--permission-record <path>` and still checks live robots rules;
it does not determine the legal validity of a supplied grant. Do not fill it with
an arbitrary acknowledgement merely to enable requests.

## Pilot and expansion

After access is resolved, run the first three seeds (one per topic):

```powershell
python -m src.ingest collect --limit 3 --permission-record <actual-permission-record.json>
python -m src.ingest validate
```

Compare each saved raw HTML with its clean Markdown and the source page. Verify
all headings, ordered/nested steps, notes, preconditions, link targets, dates and
device/OS branches; look for navigation, error pages and missing trailing
sections. The extractor accepts an `article` or `main` containing exactly one h1;
it also supports the real saved Apple `#content > #sections` container, validated
against the six user-saved files on 2026-10-24. It rejects other layouts. Stop and
adapt selectors using actual saved HTML if the layout changes. The
500-character/80-word threshold and contamination checks are
heuristics, not proof of completeness.

Only after the first three pass review, expand to all six:

```powershell
python -m src.ingest collect --limit 6 --permission-record <actual-permission-record.json>
python -m src.ingest validate
```

Requests are serial, at least 3 seconds apart, with a 20-second timeout and at
most 3 attempts for connection/timeouts or 5xx. 401/403/429 stop without retry;
redirects stop before following and require URL mapping review. Live robots
failure also blocks acquisition. `--refresh` explicitly rechecks existing
documents; default reruns validate and reuse local snapshots without network.
Run one process at a time; concurrent writers are not supported.

## Manual fallback

When a lawfully obtained local HTML or UTF-8 text file is available, preserve it
unmodified in `data/manual/`. Manual import requires an honest acquisition note,
not proof of an Apple-issued license. This distinction corrects the initial
overly broad wording: no individual written grant does not by itself establish
that every personal/non-commercial use is prohibited. Conversely, manual saving
does not automatically authorize publication, redistribution, or every RAG use.
Apple's terms include conditional informational uses; the project must stay
within applicable conditions. See `docs/MANUAL_COLLECTION_ZH.md` for practical
steps. The following note describes acquisition/use, not official permission:

```powershell
python -m src.ingest import --file data/manual/108366.html --format html --url https://support.apple.com/en-us/108366 --final-url https://support.apple.com/en-us/108366 --topic icloud --provenance "Saved manually from the public official page for local non-commercial coursework; no individual Apple permission obtained"
python -m src.ingest import --file data/manual/108366.txt --format text --title "How to back up your iPhone or iPad with iCloud" --url https://support.apple.com/en-us/108366 --topic icloud --provenance "Saved manually from the public official page for local non-commercial coursework; no individual Apple permission obtained"
python -m src.ingest validate
```

Text format must begin with the exact title (`# Title` is accepted), retain
Markdown headings (`## Section`), steps and conditions. Do not summarize or use
model-generated text. Text import preserves the original `.txt` bytes and uses
`published_at: null`; it never invents an HTML snapshot or date. HTML import
extracts a displayed Published Date as a source string if available. Final URL
defaults to the declared source URL; explicitly supply the observed URL if known.
Different article IDs/locales are rejected and require a reviewed new seed.

## Data contract

`data/sources.jsonl` contains one active record per `doc_id`:

| Field | Meaning |
|---|---|
| doc_id | `apple-<locale>-<six-digit-article-id>` |
| title | Extracted HTML title or explicitly declared text title |
| source_url / final_url | Declared source and observed/declaratively supplied final URL |
| topic / locale | Seed topic and validated URL locale |
| fetched_at | Actual ingestion timestamp in UTC with timezone (manual: import time) |
| published_at | Displayed date string from HTML, otherwise null |
| ingestion_method | `http` or `manual` |
| content_sha256 | SHA-256 of normalized clean UTF-8 text |
| snapshot_sha256 | SHA-256 of exact original bytes |
| snapshot_path / text_path | Paths relative to data root, content-versioned |
| text | Clean text used by later chunking |
| permission_basis | Legacy field name: HTTP permission basis or manual acquisition/use note; a manual note is not a license |
| human_review | `pending` until the team actually verifies this version |

Identical ID + body returns cached without adding records. Changed body replaces
the active record and retains earlier snapshots. Identical body under a different
ID is rejected for alias review. Local artifacts, hashes, required fields, URL
mapping, title, body and duplicate checks must pass. Failed HTTP extraction keeps
a diagnostic response under `data/logs/responses/`, never in the knowledge base.
Event logs are append-only; repeated event lines are history, not duplicate docs.

Only reviewed current versions should feed T03. Stage acceptance now combines
software checks, six-article AI content review and the user-confirmed full-page
check of Change your Apple Account password. See
[the archived review](reviews/DATA_REVIEW_FINAL_20261024.md). Preserve the frozen
JSONL and its legacy pending fields; record AI/user review separately in
`docs/ARTICLE_REVIEW.md`. This is not full human approval of all six articles.
Reimporting changed text requires version-specific review.

## Verification boundaries

`unittest` uses explicitly synthetic text and mocked requests in temporary
directories. These tests verify software behavior, not Apple HTML compatibility,
real acquisition, or official content correctness. A passing empty-directory
test is never six real documents. `validate` returns nonzero for empty data.

## User-saved filenames (2026-10-24)

Do not rename files just to match article numbers. The saved-file importer reads
the embedded canonical URL and verifies the h1 title against `data/seeds.json`.
Unrelated or unrecognized HTML is reported in `skipped_files`, not counted as an
import. Missing selected articles, title/canonical conflicts and duplicate selected
identities remain errors; other valid selected articles continue. Only the first
`--limit` seeds are selected. No network requests or original-file changes occur.

```powershell
python -B -m src.import_saved --limit 3 --provenance "User saved public official pages manually for local MIS2001 coursework; no individual Apple permission obtained"
python -B -m src.check_corpus
# Inspect the pilot before proceeding to all six.
python -B -m src.import_saved --limit 6 --provenance "User saved public official pages manually for local MIS2001 coursework; no individual Apple permission obtained"
python -B -m src.ingest validate
python -B -m src.check_corpus
```

`src.check_corpus` compares each current snapshot's information-bearing paragraphs
in source order, heading order, list numbers and links with the clean text. It
checks for known navigation/feedback artifacts. Generic “Need more help?” content
is excluded; factual support contact links and disclaimers elsewhere are retained.
Structural checks do not replace human review. All six passed in
the local record `evidence/corpus_quality_20261024.json` (ignored; not supplied in
a public checkout).

Text snapshots receive the same metadata, body, file and hash checks first.
They report `html_structure_status: not_applicable`, with no invented HTML metrics.
`passed` means applicable checks passed; summaries separate HTML passes from text
records. Individual bad records, including malformed JSONL lines, remain in the
report while other articles continue. Any failure or an empty corpus causes a
nonzero exit code. Reports under `evidence/` and event logs remain local.

For these manual files, `final_url` is the canonical URL embedded in the saved
page, not a newly verified HTTP redirect destination. `fetched_at` is import time;
the exact original browser download time is not inferred from file mtime.
