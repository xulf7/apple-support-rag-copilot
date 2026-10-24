"""Small, auditable ingestion CLI. No embeddings, model calls, or UI.

HTTP requires a documented permission record AND a successful robots check.
Manual import records how a local file was obtained; it does not assert a license.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

USER_AGENT = "MIS2001AcademicIngest/0.1"


def validate_topic(topic):
    """Topic is descriptive metadata, not a runtime business-scope allowlist."""
    if (not isinstance(topic, str) or not topic.strip() or topic != topic.strip()
            or len(topic) > 80 or any(ord(c) < 32 for c in topic)):
        raise ValueError("Topic must be a nonempty label of up to 80 characters without control characters")
    return topic


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def identity(url):
    p = urlparse(url)
    match = re.fullmatch(r"/([a-z]{2}-[a-z]{2})/(\d{6})/?", p.path)
    if (p.scheme != "https" or p.netloc != "support.apple.com" or
            p.query or p.fragment or not match):
        raise ValueError("Expected a direct HTTPS support.apple.com/<locale>/<article-id> URL")
    locale, article = match.groups()
    return f"apple-{locale}-{article}", locale


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def log_event(root, **event):
    path = root / "logs/events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now(), **event}, ensure_ascii=False) + "\n")


def inline(node):
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    if node.name == "br":
        return "\n"
    text = "".join(inline(c) for c in node.children)
    if node.name == "a" and node.get("href"):
        return f"[{text.strip()}]({node['href']})"
    if node.name == "img":
        return f" [Image: {node.get('alt', '')}] " if node.get("alt") else ""
    if node.name in {"p", "div"}:
        return text + "\n"
    return text


def blocks(node, depth=0):
    """Keep headings, paragraph order, nested lists, tables and linked evidence."""
    result = []
    for child in node.children:
        if isinstance(child, NavigableString):
            if child.strip():
                result.append(str(child).strip())
            continue
        tag = child.name
        if re.fullmatch(r"h[1-6]", tag or ""):
            result.append("#" * int(tag[1]) + " " + inline(child).strip())
        elif tag in ("ol", "ul"):
            number = int(child.get("start", 1))
            for li in child.find_all("li", recursive=False):
                if li.get("value"):
                    number = int(li["value"])
                prefix = f"{number}. " if tag == "ol" else "- "
                direct = "".join(inline(c) for c in li.children if not (isinstance(c, Tag) and c.name in ("ol", "ul")))
                result.append("  " * depth + prefix + re.sub(r"\s+", " ", direct).strip())
                for nested in li.find_all(["ol", "ul"], recursive=False):
                    wrapper = BeautifulSoup("<div></div>", "html.parser").div
                    wrapper.append(BeautifulSoup(str(nested), "html.parser"))
                    result.extend(blocks(wrapper, depth + 1))
                number += 1
        elif tag == "table":
            for row in child.find_all("tr"):
                result.append(" | ".join(inline(c).strip() for c in row.find_all(["th", "td"], recursive=False)))
        elif tag in ("p", "blockquote", "pre", "figcaption", "a"):
            result.append(inline(child).strip())
        else:
            result.extend(blocks(child, depth))
    return [line for line in result if line]


def validate_text(title, text):
    if not title.strip() or len(text) < 500 or len(text.split()) < 80:
        raise ValueError("Missing title or insufficient article body (500 characters / 80 words)")
    if not re.search(r"^#{2,6} .+", text, re.M):
        raise ValueError("No section headings: retain the official heading structure")
    if title.strip() not in text.splitlines()[0]:
        raise ValueError("First line must contain the article title")


def prune_chrome(container):
    """Remove identified DOM regions, never classify an article by its wording."""
    for node in container.select("nav, footer, script, style, form, button, input, select, noscript, [role=navigation], .ac-gf-footer, #article-helpful, .helpful, .article-feedback, .content-type-dropdown"):
        node.decompose()
    # Apple marks its generic contact CTA as an icon action in a direct section
    # group. A heading such as 'Need more help?' alone is ordinary article text.
    for group in container.find_all(class_="gb-group"):
        if (group.parent is None or group.parent.get("id") != "sections"
                or group.find(["ol", "ul", "table", "pre"])):
            continue
        if any(a.get("link-type") == "ICON" and a.get("href", "").startswith("https://getsupport.apple.com/")
               for p in group.find_all("p", recursive=False)
               for a in p.find_all("a", recursive=False)):
            group.decompose()


def extract_html(raw, final_url):
    soup = BeautifulSoup(raw, "html.parser")
    # Fail closed if Apple changes its article structure; never use the whole body.
    container = soup.select_one("#content > #sections") or soup.select_one("article") or soup.select_one("main")
    if container is None or len(container.find_all("h1")) != 1:
        raise ValueError("Expected an Apple #content > #sections or article/main container with exactly one h1")
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and identity(canonical.get("href", "")) != identity(final_url):
        raise ValueError("HTML canonical URL does not match the declared article/locale")
    title = container.h1.get_text(" ", strip=True)
    published = None
    for item in container.find_all(["p", "div", "time"]):
        plain = item.get_text(" ", strip=True)
        if plain.startswith("Published Date:") and len(plain) < 100:
            published = plain.split(":", 1)[1].strip() or None
    prune_chrome(container)
    for a in container.find_all("a", href=True):
        a["href"] = urljoin(final_url, a["href"])
    text = "\n\n".join(blocks(container)).strip() + "\n"
    validate_text(title, text)
    return title, text, published


def check_record(root, record):
    required = {"doc_id", "title", "source_url", "final_url", "topic", "locale", "fetched_at",
                "published_at", "ingestion_method", "content_sha256", "snapshot_path", "text", "text_path",
                "snapshot_sha256", "permission_basis", "human_review"}
    if not required <= record.keys():
        raise ValueError("Incomplete metadata")
    doc_id, locale = identity(record["source_url"])
    if identity(record["final_url"]) != (doc_id, locale):
        raise ValueError("Source/final URL article or locale mismatch")
    if record["doc_id"] != doc_id or record["locale"] != locale:
        raise ValueError("Document identity mismatch")
    validate_topic(record["topic"])
    if record["ingestion_method"] not in {"http", "manual"} or not record["permission_basis"].strip():
        raise ValueError("Missing import provenance")
    if datetime.fromisoformat(record["fetched_at"]).tzinfo is None:
        raise ValueError("Collection timestamp must have timezone")
    validate_text(record["title"], record["text"])
    if digest(record["text"]) != record["content_sha256"]:
        raise ValueError("Content hash mismatch")
    for field in ("snapshot_path", "text_path"):
        p = (root / record[field]).resolve()
        if not p.is_relative_to(root.resolve()):
            raise ValueError("Artifact path escapes data directory")
        if not p.is_file():
            raise ValueError(f"Missing artifact: {field}")
    if (root / record["text_path"]).read_text(encoding="utf-8") != record["text"]:
        raise ValueError("Clean text does not match metadata")
    if hashlib.sha256((root / record["snapshot_path"]).read_bytes()).hexdigest() != record["snapshot_sha256"]:
        raise ValueError("Snapshot hash mismatch")


def store(root, seed, raw, final_url, method, permission_basis, fmt="html", title=None):
    if not permission_basis.strip():
        raise ValueError("Describe the source and acquisition method; do not invent permission")
    doc_id, locale = identity(seed["source_url"])
    if identity(final_url) != (doc_id, locale):
        raise ValueError("Redirect changed article ID or locale; review URL mapping before import")
    validate_topic(seed["topic"])
    if fmt == "html":
        title, text, published = extract_html(raw.decode("utf-8-sig"), final_url)
    else:
        text = raw.decode("utf-8-sig").replace("\r\n", "\n").strip() + "\n"
        published = None  # Do not infer dates from manual text.
        validate_text(title or "", text)
    rows = read_jsonl(root / "sources.jsonl")
    content_hash = digest(text)
    previous = next((r for r in rows if r["doc_id"] == doc_id), None)
    if previous and previous["content_sha256"] == content_hash:
        check_record(root, previous)
        return "cached", previous
    duplicate = next((r for r in rows if r["content_sha256"] == content_hash and r["doc_id"] != doc_id), None)
    if duplicate:
        raise ValueError(f"Identical body already belongs to {duplicate['doc_id']}; review alias")
    # Versioned artifacts retain evidence from earlier successful imports.
    version = hashlib.sha256(raw).hexdigest()
    snapshot = f"raw/{doc_id}-{version[:16]}.{ 'html' if fmt == 'html' else 'txt'}"
    clean = f"clean/{doc_id}-{content_hash[:16]}.md"
    (root / "raw").mkdir(parents=True, exist_ok=True)
    (root / snapshot).write_bytes(raw)
    atomic_text(root / clean, text)
    record = dict(doc_id=doc_id, title=title, source_url=seed["source_url"], final_url=final_url,
                  topic=seed["topic"], locale=locale, fetched_at=now(), published_at=published,
                  ingestion_method=method, content_sha256=content_hash, snapshot_sha256=version,
                  snapshot_path=snapshot, text_path=clean, text=text, permission_basis=permission_basis,
                  human_review="pending")
    check_record(root, record)
    rows = [r for r in rows if r["doc_id"] != doc_id] + [record]
    atomic_text(root / "sources.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in sorted(rows, key=lambda r: r["doc_id"])))
    return "success", record


class Fetcher:
    def __init__(self, delay=3, attempts=3, timeout=20):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.delay, self.attempts, self.timeout = max(3, delay), attempts, timeout
        self.last = 0.0

    def get(self, url):
        for attempt in range(self.attempts):
            time.sleep(max(0, self.delay - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            try:
                r = self.session.get(url, timeout=self.timeout, allow_redirects=False)
                if r.status_code in (401, 403, 429):
                    raise ValueError(f"Access restricted HTTP {r.status_code}; stopped without retry")
                if r.is_redirect:
                    raise ValueError(f"Redirect to {r.headers.get('Location')}; review final URL before request")
                if r.status_code >= 500 and attempt + 1 < self.attempts:
                    continue
                r.raise_for_status()
                return r
            except (requests.Timeout, requests.ConnectionError):
                if attempt + 1 == self.attempts:
                    raise
        raise RuntimeError("Retry limit reached")


def collect(root, seeds, grant=None, refresh=False):
    permission = json.loads(Path(grant).read_text(encoding="utf-8")) if grant else {}
    fetcher = Fetcher()
    robots = None
    outcomes = []
    for seed in seeds:
        url = seed["source_url"]
        try:
            doc_id, _ = identity(url)
            if not refresh:
                old = next((r for r in read_jsonl(root / "sources.jsonl") if r["doc_id"] == doc_id), None)
                if old:
                    check_record(root, old)
                    outcomes.append("cached")
                    log_event(root, source_url=url, status="cached", doc_id=doc_id)
                    continue
            if not (permission.get("basis", "").strip() and url in permission.get("allowed_urls", [])):
                raise PermissionError("Automatic collection blocked: Apple terms restriction; documented applicable permission required")
            if robots is None:
                response = fetcher.get("https://support.apple.com/robots.txt")
                robots = RobotFileParser()
                robots.parse(response.text.splitlines())
                atomic_text(root / "logs/robots.txt", response.text)
            if not robots.can_fetch(USER_AGENT, url):
                raise PermissionError("robots.txt disallows this URL")
            response = fetcher.get(url)
            raw = response.content
            # Keep failed-response snapshots for diagnosis, outside the knowledge base.
            atomic_text(root / f"logs/responses/{doc_id}.html", raw.decode("utf-8", errors="replace"))
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("Unexpected Content-Type")
            status, record = store(root, seed, raw, response.url, "http", permission["basis"])
            log_event(root, source_url=url, status=status, doc_id=record["doc_id"])
            outcomes.append(status)
        except (ValueError, OSError, requests.RequestException) as exc:
            # Exception strings from requests may contain proxy credentials; log class only.
            reason = type(exc).__name__ if isinstance(exc, requests.RequestException) else str(exc)
            if isinstance(exc, requests.RequestException) and exc.response is not None:
                reason += f" HTTP {exc.response.status_code}"
            status = "blocked" if isinstance(exc, PermissionError) else "failed"
            log_event(root, source_url=url, status=status, reason=reason)
            outcomes.append(status)
    return {name: outcomes.count(name) for name in ("success", "cached", "blocked", "failed")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("collect")
    p.add_argument("--seeds", type=Path, default=Path("data/seeds.json"))
    p.add_argument("--limit", type=int, default=6)
    p.add_argument("--permission-record", type=Path)
    p.add_argument("--refresh", action="store_true")
    p = sub.add_parser("import")
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--final-url")
    p.add_argument("--topic", type=validate_topic, required=True, help="Descriptive topic label; no fixed topic catalog")
    p.add_argument("--format", choices=["html", "text"], required=True)
    p.add_argument("--title", help="Required for text; first line must contain this title")
    p.add_argument("--provenance", dest="permission_basis", required=True,
                   help="How this local file was obtained and intended use; not a claim of official permission")
    sub.add_parser("validate")
    args = parser.parse_args()
    root = args.data_dir
    try:
        if args.command == "collect":
            if args.limit < 1:
                raise ValueError("limit must be positive")
            result = collect(root, json.loads(args.seeds.read_text(encoding="utf-8"))[:args.limit], args.permission_record, args.refresh)
            print(json.dumps(result))
            return int(bool(result["failed"] or result["blocked"]))
        if args.command == "import":
            try:
                status, record = store(root, {"source_url": args.url, "topic": args.topic}, args.file.read_bytes(),
                                       args.final_url or args.url, "manual", args.permission_basis, args.format, args.title)
                log_event(root, status=status, source_url=args.url, doc_id=record["doc_id"])
                print(json.dumps({"status": status, "doc_id": record["doc_id"], "human_review": record["human_review"]}))
                return 0
            except (ValueError, OSError) as exc:
                log_event(root, status="failed", source_url=args.url, reason=str(exc))
                raise
        rows = read_jsonl(root / "sources.jsonl")
        ids, hashes = set(), set()
        for row in rows:
            check_record(root, row)
            if row["doc_id"] in ids or row["content_sha256"] in hashes:
                raise ValueError("Duplicate document ID or body hash")
            ids.add(row["doc_id"])
            hashes.add(row["content_sha256"])
        print(json.dumps({"documents": len(rows), "structural_checks": "passed" if rows else "empty_corpus",
                          "human_review_pending": sum(r["human_review"] == "pending" for r in rows)}))
        return 0 if rows else 1
    except (ValueError, OSError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
