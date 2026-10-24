"""Compare snapshot structure, paragraph coverage and retained rendered text.

This is a structural comparison, not human approval of Apple procedures.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.ingest import atomic_text, blocks, check_record, now, prune_chrome


def compact(text):
    return re.sub(r"\W+", "", text, flags=re.UNICODE).casefold()


def audit(root, row):
    check_record(root, row)
    suffix = Path(row["snapshot_path"]).suffix.lower()
    if suffix == ".txt":
        return {"doc_id": row["doc_id"], "title": row["title"],
                "integrity_check": "passed", "html_structure_status": "not_applicable",
                "reason": "Text snapshot: HTML paragraph, heading, step and link comparisons are not applicable",
                "human_review": row["human_review"], "passed": True,
                "review_note": "Text integrity is not semantic approval; compare with the official source manually."}
    if suffix not in {".html", ".htm"}:
        raise ValueError("Unsupported snapshot format")
    soup = BeautifulSoup((root / row["snapshot_path"]).read_bytes(), "html.parser")
    body = soup.select_one("#content > #sections") or soup.select_one("article") or soup.select_one("main")
    if body is None or len(body.find_all("h1")) != 1:
        raise ValueError("Snapshot lacks an article container with exactly one h1")
    prune_chrome(body)
    clean = row["text"]
    plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", clean)
    flat = compact(plain)
    paragraphs = body.find_all("p")
    missing = [p.get_text(" ", strip=True) for p in paragraphs
               if compact(p.get_text(" ", strip=True)) not in flat]
    cursor = 0
    paragraphs_in_order = True
    for p in paragraphs:
        value = compact(p.get_text(" ", strip=True))
        if not value:
            continue
        position = flat.find(value, cursor)
        if position < 0:
            paragraphs_in_order = False
            break
        cursor = position + len(value)
    headings = [(h.name, h.get_text(" ", strip=True)) for h in body.find_all(re.compile(r"^h[1-6]$"))]
    actual_headings = [line for line in clean.splitlines() if re.match(r"^#{1,6} ", line)]
    expected_headings = ["#" * int(tag[1]) + " " + title for tag, title in headings]
    expected_numbers = []
    for ol in body.find_all("ol"):
        number = int(ol.get("start", 1))
        for li in ol.find_all("li", recursive=False):
            number = int(li.get("value", number))
            expected_numbers.append(number)
            number += 1
    actual_numbers = [int(n) for n in re.findall(r"^\s*(\d+)\. ", clean, re.M)]
    expected_links = {urljoin(row["final_url"], a["href"]) for a in body.find_all("a", href=True)
                      if a.get_text(" ", strip=True) and not a.find_parent(class_="videoComponentContainer")}
    # Generic media playback links are outside the text knowledge base.
    missing_links = sorted(link for link in expected_links if f"]({link})" not in clean)
    # Independent paragraph/heading/step/link checks above are supplemented by
    # full rendered-body coverage. Extra navigation/feedback text cannot pass
    # merely because all real paragraphs are also present. Normalize formatting,
    # not wording: legitimate error names and device instructions remain valid.
    expected_body = "\n\n".join(blocks(body))
    expected_plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", expected_body)
    body_matches = flat == compact(expected_plain)
    result = {"doc_id": row["doc_id"], "title": row["title"], "paragraphs_checked": len(paragraphs),
              "missing_paragraphs": missing, "paragraphs_in_order": paragraphs_in_order, "headings_checked": len(headings),
              "headings_in_order": actual_headings == expected_headings,
              "ordered_steps_checked": len(expected_numbers), "ordered_step_numbers_match": actual_numbers == expected_numbers,
              "links_checked": len(expected_links), "missing_links": missing_links,
              "body_matches_snapshot": body_matches, "human_review": row["human_review"],
              "review_note": "Structure checks cannot determine semantic validity; manual content review remains necessary."}
    result["passed"] = not (missing or missing_links) and body_matches and paragraphs_in_order and result["headings_in_order"] and result["ordered_step_numbers_match"]
    result["integrity_check"] = "passed"
    result["html_structure_status"] = "passed" if result["passed"] else "failed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--report", type=Path, default=Path("evidence/corpus_quality_latest.json"))
    args = parser.parse_args()
    path = args.data_dir / "sources.jsonl"
    rows, results, ids, hashes = [], [], set(), set()
    unique = True
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        row = None
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("Document record must be a JSON object")
            rows.append(row)
            result = audit(args.data_dir, row)
            if row["doc_id"] in ids or row["content_sha256"] in hashes:
                unique = False
                raise ValueError("Duplicate document ID or body hash")
            ids.add(row["doc_id"])
            hashes.add(row["content_sha256"])
        except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
            result = {"doc_id": row.get("doc_id") if isinstance(row, dict) else None,
                      "passed": False, "html_structure_status": "not_completed",
                      "error": f"{type(exc).__name__}: {exc}"}
        results.append({"line": line_number, **result})
    summary = {"documents": len(results), "passed": sum(r["passed"] for r in results),
               "failed": sum(not r["passed"] for r in results),
               "html_structural_passed": sum(r["html_structure_status"] == "passed" for r in results),
               "html_structural_not_applicable": sum(r["html_structure_status"] == "not_applicable" for r in results),
               "unique_ids_and_hashes": unique,
               "topics": dict(Counter(r["topic"] for r in rows if isinstance(r.get("topic"), str))),
               "human_review_pending": sum(r.get("human_review") == "pending" for r in rows)}
    atomic_text(args.report, json.dumps({"executed_at": now(), "summary": summary, "results": results}, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary))
    return 0 if results and unique and all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
