#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Build a self-contained AI-news feed.html from curated X handles via Firecrawl."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = SKILL_DIR / "sources.json"
DEFAULT_TEMPLATE = SKILL_DIR / "assets" / "template.html"
DEFAULT_OUTPUT = Path.home() / "x-ai-feed" / "feed.html"

FIRECRAWL_CONCURRENCY = 2
SCRAPE_TIMEOUT_SECS = 90
SCRAPE_ATTEMPTS = 2
SCRAPE_RETRY_DELAY_SECS = 5

HEADER_RE = re.compile(r"^#\s*(?P<name>.+?)\s*\(@(?P<handle>\w+)\)", re.MULTILINE)
VERIFIED_RE = re.compile(r"^-\s*Verified:\s*(yes|no)", re.MULTILINE | re.IGNORECASE)
POST_BLOCK_RE = re.compile(
    r"###\s*\d+\.\s*Post\s*\n"
    r"Posted:\s*(?P<posted>.+?)\s*\n"
    r"URL:\s*\[[^\]]*\]\((?P<url>[^)\s]+)\)\s*\n"
    r"\n?"
    r"(?P<quote>.*?)"
    r"\n\s*Likes:\s*(?P<likes>[\d,]+)\s*\|\s*Retweets:\s*(?P<retweets>[\d,]+)",
    re.DOTALL,
)
ESCAPED_MD_RE = re.compile(r"\\([\-\.\_\*\[\]\(\)\#\+\!])")


@dataclass
class Post:
    handle: str
    author: str
    verified: bool
    category: str
    posted: str
    url: str
    text: str
    likes: int
    retweets: int


def unescape(text: str) -> str:
    return html.unescape(ESCAPED_MD_RE.sub(r"\1", text))


def parse_int(text: str) -> int:
    return int(text.replace(",", ""))


def parse_posted(raw: str) -> datetime | None:
    """Profile scrapes render post timestamps as either ISO-8601 or RFC-822; accept both."""
    raw = raw.strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def safe_post_url(raw: str) -> str | None:
    url = unescape(raw)
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "twitter.com",
        "www.twitter.com",
        "x.com",
        "www.x.com",
    }:
        return None
    return url


def parse_profile(markdown: str, handle: str, category: str) -> tuple[list[Post], str]:
    header = HEADER_RE.search(markdown)
    author = unescape(header.group("name")) if header else handle
    verified_match = VERIFIED_RE.search(markdown)
    verified = bool(verified_match and verified_match.group(1).lower() == "yes")

    posts = []
    for block in POST_BLOCK_RE.finditer(markdown):
        quote_lines = [
            re.sub(r"^>\s?", "", line)
            for line in block.group("quote").strip("\n").splitlines()
        ]
        text = unescape("\n".join(quote_lines).strip())
        if not text:
            continue
        posted_dt = parse_posted(unescape(block.group("posted")))
        if posted_dt is None:
            continue
        url = safe_post_url(block.group("url"))
        if url is None:
            continue
        posts.append(
            Post(
                handle=handle,
                author=author,
                verified=verified,
                category=category,
                posted=posted_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                url=url,
                text=text,
                likes=parse_int(block.group("likes")),
                retweets=parse_int(block.group("retweets")),
            )
        )
    return posts, author


def scrape_handle(handle: str) -> tuple[str, str | None]:
    for attempt in range(1, SCRAPE_ATTEMPTS + 1):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            result = subprocess.run(
                ["firecrawl", "scrape", f"https://x.com/{handle}", "-o", str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=SCRAPE_TIMEOUT_SECS,
            )
            if result.returncode == 0:
                content = tmp_path.read_text(encoding="utf-8")
                if content.strip():
                    return handle, content
        except (subprocess.TimeoutExpired, OSError):
            pass
        finally:
            tmp_path.unlink(missing_ok=True)
        if attempt < SCRAPE_ATTEMPTS:
            time.sleep(SCRAPE_RETRY_DELAY_SECS)
    return handle, None


def build_feed(
    sources_path: Path,
    lookback_hours: int,
    max_stories: int,
) -> tuple[list[Post], dict]:
    config = json.loads(sources_path.read_text(encoding="utf-8"))
    sources = config["sources"]
    category_by_handle = {s["handle"]: s["category"] for s in sources}

    all_posts: list[Post] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=FIRECRAWL_CONCURRENCY) as pool:
        for handle, markdown in pool.map(scrape_handle, category_by_handle):
            if markdown is None:
                errors.append(handle)
                continue
            posts, _ = parse_profile(markdown, handle, category_by_handle[handle])
            all_posts.extend(posts)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    seen_urls: set[str] = set()
    fresh: list[Post] = []
    for post in all_posts:
        posted_dt = datetime.fromisoformat(post.posted.replace("Z", "+00:00"))
        if posted_dt < cutoff or post.url in seen_urls:
            continue
        seen_urls.add(post.url)
        fresh.append(post)

    fresh.sort(key=lambda p: p.posted, reverse=True)
    fresh = fresh[:max_stories]

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lookback_hours": lookback_hours,
        "source_count": len(category_by_handle),
        "story_count": len(fresh),
        "errors": errors,
        "categories": config.get("categories", sorted({s["category"] for s in sources})),
    }
    return fresh, meta


def json_for_script(value) -> str:
    """json.dumps, but safe to inline in a <script> tag (guards against '</script>' in content)."""
    return json.dumps(value).replace("</", "<\\/")


def render(posts: list[Post], meta: dict, template_path: Path, output_path: Path) -> None:
    template = template_path.read_text(encoding="utf-8")
    rendered = template.replace(
        "__FEED_DATA_JSON__", json_for_script([asdict(p) for p in posts])
    ).replace("__META_JSON__", json_for_script(meta))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--max-stories", type=int, default=60)
    args = parser.parse_args()

    posts, meta = build_feed(args.sources, args.lookback_hours, args.max_stories)
    render(posts, meta, args.template, args.output)

    print(f"wrote {len(posts)} stories from {meta['source_count']} sources to {args.output}")
    if meta["errors"]:
        print(f"unavailable this run: {', '.join(meta['errors'])}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
