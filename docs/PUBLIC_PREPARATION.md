# Public source preparation — 2026-10-24

This maintenance round fixes two reproduced data-preparation boundaries. It does
not implement T03-T04 or change the extraction/ingestion data contract.

- Text snapshots receive existing metadata, artifact, body and hash checks. HTML
  comparison is explicitly `not_applicable`; HTML pass counts exclude these
  records. Bad records remain in the report and cause nonzero overall status
  without hiding other article results.
- Unrelated or unrecognized saved HTML is separately reported as skipped. Only
  selected seed articles are required. Missing selected files, title/canonical
  conflicts and duplicate selected identities remain errors; other valid articles
  continue. Skips never count as imports.

## Public files

Source, synthetic tests, dependencies, empty `.env.example`, URL-only seeds,
README, usage instructions, review checklist, task progress and short data results.
Personal member names were replaced by roles in the public tracker. Student IDs,
real credentials and machine-specific absolute paths do not belong in these files.
No open-source license was chosen; third-party Apple material is not included in
any project code license.

## Local files

`.gitignore` excludes `library/`, original/snapshot/clean article text, full-text
`data/sources.jsonl`, logs, raw evidence, the original environment report, secrets,
caches, environments, future model/index output and local review packages. It does
not delete any of them. All existing versions, including three historical clean
versions, are retained. Only `sources.jsonl` defines the active corpus.

Raw evidence is kept locally under `evidence/public_prep_20261024/`, intentionally
absent from a public checkout. Editable documentation was backed up there before
public edits. Protected files were hashed before changes and checked at completion.

## Verification

```powershell
python -B -m unittest discover -s tests -v
# These require a locally imported corpus:
python -B -m src.ingest validate
python -B -m src.check_corpus --report evidence/public_prep_20261024/corpus.json
```

29 synthetic tests pass, including the new boundary cases. The suite is also
checked in a temporary copy of only public candidate files, without real data,
references or historical evidence. Six current HTML articles still pass integrity
and structure checks; team human review remains pending. Ignore rules are checked
with Git in a separate temporary sandbox, for real files and representative
future outputs. This does not initialize the project directory.

Recorded results: 50 ignored-path probes and 13 public-path probes passed. A
targeted scan of 18 public candidate files found no credential tokens, student
IDs, member names or machine-specific absolute paths; public Markdown links
resolved to public candidates. This is a scoped check, not a claim about other
repositories or unseen secrets. All 49 protected original files matched their
preparation-time hashes. Six manual originals, six raw snapshots, all nine clean
versions and existing evidence were preserved; the new reports use new filenames.

## Git state and limits

Actual Git probes in the project and its parent hierarchy reported `not a git
repository`. No current branch, remote, tracked file list or commit history is
available here. This is based on Git commands, not assumptions about a ZIP.
Another checkout or remote GitHub history has not been inspected. No staging,
commit, push, remote change or history rewrite was performed.

Ignore rules do not remove tracked files or prior commits. If copied into an
existing repository later, inspect that repository's tracked paths and history
first. A targeted command such as `git rm --cached -- data/sources.jsonl` would
untrack that named file without deleting the local file, but stages a deletion
and should only be run after review in that repository. No such command was run
this round. `.gitignore` never establishes that historical sensitive content was
removed.
