#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Search and list YouTube knowledge base entries.

Usage:
    uv run search_knowledge.py --list              # List recent analyses
    uv run search_knowledge.py "react hooks"       # Search by keyword
    uv run search_knowledge.py --tag ai            # Filter by tag

Environment:
    CLAUDE_KNOWLEDGE_DIR: Knowledge base directory (default: ~/.claude/knowledge)
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import TypedDict

import yaml


class AnalysisEntry(TypedDict):
    path: str
    video_id: str
    title: str
    channel: str
    duration: str
    analyzed: str
    analysis_mode: str
    tags: list[str]


def get_knowledge_dir() -> Path:
    """Get the knowledge base directory from env or default."""
    default = Path.home() / ".claude" / "knowledge"
    env_dir = os.environ.get("CLAUDE_KNOWLEDGE_DIR")
    return Path(env_dir) if env_dir else default


def parse_frontmatter(filepath: Path) -> dict | None:
    """Extract YAML frontmatter from a markdown file."""
    try:
        content = filepath.read_text()
        if not content.startswith("---"):
            return None

        end_match = re.search(r"\n---\n", content[3:])
        if not end_match:
            return None

        yaml_content = content[3 : end_match.start() + 3]
        return yaml.safe_load(yaml_content)
    except Exception:
        return None


def get_all_entries(knowledge_dir: Path) -> list[AnalysisEntry]:
    """Get all analysis entries from the knowledge base."""
    analyses_dir = knowledge_dir / "youtube" / "analyses"
    if not analyses_dir.exists():
        return []

    entries = []
    for filepath in sorted(analyses_dir.glob("*.md"), reverse=True):
        frontmatter = parse_frontmatter(filepath)
        if frontmatter:
            entries.append({
                "path": str(filepath),
                "video_id": frontmatter.get("video_id", ""),
                "title": frontmatter.get("title", "Unknown"),
                "channel": frontmatter.get("channel", "Unknown"),
                "duration": frontmatter.get("duration", ""),
                "analyzed": frontmatter.get("analyzed", "")[:10],
                "analysis_mode": frontmatter.get("analysis_mode", ""),
                "tags": frontmatter.get("tags", []),
            })

    return entries


def filter_by_tag(entries: list[AnalysisEntry], tag: str) -> list[AnalysisEntry]:
    """Filter entries by tag."""
    tag_lower = tag.lower()
    return [e for e in entries if tag_lower in [t.lower() for t in e["tags"]]]


def search_entries(
    entries: list[AnalysisEntry], query: str, knowledge_dir: Path
) -> list[AnalysisEntry]:
    """Search entries by keyword in title, channel, or content."""
    query_lower = query.lower()
    results = []

    for entry in entries:
        # Check frontmatter fields
        if (
            query_lower in entry["title"].lower()
            or query_lower in entry["channel"].lower()
            or query_lower in " ".join(entry["tags"]).lower()
        ):
            results.append(entry)
            continue

        # Check file content
        filepath = Path(entry["path"])
        if filepath.exists():
            content = filepath.read_text().lower()
            if query_lower in content:
                results.append(entry)

    return results


def format_entry(entry: AnalysisEntry, verbose: bool = False) -> str:
    """Format an entry for display."""
    tags_str = ", ".join(entry["tags"]) if entry["tags"] else "-"
    line = f"{entry['analyzed']}  {entry['title'][:50]:<50}  {entry['channel'][:20]:<20}  {entry['analysis_mode']:<10}"

    if verbose:
        line += f"\n          Tags: {tags_str}"
        line += f"\n          Path: {entry['path']}"

    return line


def main():
    parser = argparse.ArgumentParser(description="Search YouTube knowledge base")
    parser.add_argument(
        "query",
        nargs="?",
        help="Search query (searches title, channel, tags, and content)",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List all recent analyses",
    )
    parser.add_argument(
        "--tag",
        "-t",
        help="Filter by tag",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=20,
        help="Maximum results to show (default: 20)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show more details",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    knowledge_dir = get_knowledge_dir()
    entries = get_all_entries(knowledge_dir)

    if not entries:
        if args.json:
            print("[]")
        else:
            print(f"No analyses found in {knowledge_dir}/youtube/analyses/")
        return

    # Apply filters
    if args.tag:
        entries = filter_by_tag(entries, args.tag)

    if args.query:
        entries = search_entries(entries, args.query, knowledge_dir)

    # Limit results
    entries = entries[: args.limit]

    # Output
    if args.json:
        import json

        print(json.dumps(entries, indent=2))
    else:
        if not entries:
            print("No matching analyses found.")
            return

        print(f"{'Date':<12}{'Title':<52}{'Channel':<22}{'Mode':<10}")
        print("-" * 96)
        for entry in entries:
            print(format_entry(entry, args.verbose))

        print(f"\n{len(entries)} result(s) from {knowledge_dir}")


if __name__ == "__main__":
    main()
