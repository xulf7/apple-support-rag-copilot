"""Import user-saved official HTML by canonical URL, independent of file names.

Run the first three seeds and inspect the pilot before importing all six.
No network requests are made. Original files are never renamed or modified.
"""
import argparse
import json
from pathlib import Path
import sys

from bs4 import BeautifulSoup

from src.ingest import atomic_text, identity, log_event, now, store


def discover(folder, seeds):
    allowed = {identity(seed["source_url"]): seed for seed in seeds}
    found, skipped, errors, seen = {}, [], {}, set()
    for file in sorted(folder.iterdir()):
        if file.suffix.lower() not in {".html", ".htm"} or not file.is_file():
            continue
        try:
            soup = BeautifulSoup(file.read_bytes(), "html.parser")
        except OSError as exc:
            skipped.append({"file": file.as_posix(), "reason": f"Unreadable HTML: {type(exc).__name__}"})
            continue
        h1 = soup.find_all("h1")
        title = h1[0].get_text(" ", strip=True) if len(h1) == 1 else None
        canonical = soup.select_one('link[rel="canonical"]')
        try:
            if canonical is None:
                raise ValueError("No canonical source URL")
            key = identity(canonical.get("href", ""))
            if key not in allowed:
                raise ValueError("Canonical URL is outside the selected seed articles")
        except ValueError as exc:
            # A recognizable selected title with a bad canonical is a target error.
            suspected = [k for k, seed in allowed.items() if title == seed["observed_title"]]
            if suspected:
                for key in suspected:
                    errors.setdefault(key, []).append(f"{file.name}: {exc}")
                    found.pop(key, None)
            else:
                skipped.append({"file": file.as_posix(), "reason": str(exc)})
            continue
        if key in seen:
            errors.setdefault(key, []).append(f"Multiple files map to the same article: {file.name}")
        seen.add(key)
        if len(h1) != 1 or h1[0].get_text(" ", strip=True) != allowed[key]["observed_title"]:
            errors.setdefault(key, []).append(f"Saved title does not match seed: {file.name}")
        if key in errors:
            found.pop(key, None)
        else:
            found[key] = (file, canonical["href"])
    return found, skipped, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual-dir", type=Path, default=Path("data/manual"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--seeds", type=Path, default=Path("data/seeds.json"))
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--report", type=Path, default=Path("evidence/manual_import_latest.json"))
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    results = []
    try:
        seeds = json.loads(args.seeds.read_text(encoding="utf-8"))
        seeds = seeds[:args.limit]
        found, skipped, errors = discover(args.manual_dir, seeds)
    except (ValueError, OSError) as exc:
        log_event(args.data_dir, status="failed", stage="manual_discovery", reason=str(exc))
        print(str(exc), file=sys.stderr)
        return 1
    for skipped_file in skipped:
        log_event(args.data_dir, stage="manual_discovery", status="skipped", **skipped_file)
    for seed in seeds:
        source = seed["source_url"]
        try:
            key = identity(source)
            if key in errors:
                raise ValueError("; ".join(errors[key]))
            match = found.get(key)
            if match is None:
                raise ValueError("No matching saved HTML file")
            file, final_url = match
            status, row = store(args.data_dir, seed, file.read_bytes(), final_url,
                                "manual", args.provenance)
            result = {"source_url": source, "original_file": file.as_posix(), "status": status,
                      "doc_id": row["doc_id"], "title": row["title"],
                      "snapshot_path": row["snapshot_path"], "text_path": row["text_path"],
                      "content_sha256": row["content_sha256"], "characters": len(row["text"]),
                      "published_at": row["published_at"], "human_review": row["human_review"]}
        except (ValueError, OSError) as exc:
            result = {"source_url": source, "status": "failed", "reason": str(exc)}
        results.append(result)
        log_event(args.data_dir, stage="manual_import", **result)
    summary = {key: sum(row["status"] == key for row in results) for key in ("success", "cached", "failed")}
    summary["skipped"] = len(skipped)
    atomic_text(args.report, json.dumps({"executed_at": now(), "summary": summary,
                                       "results": results, "skipped_files": skipped}, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary))
    return int(bool(summary["failed"]))


if __name__ == "__main__":
    sys.exit(main())
