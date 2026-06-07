#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Save YouTube video analysis and raw transcript to the knowledge base.

Saves two files:
- analyses/{date}_{video_id}.md: Formatted analysis with frontmatter
- transcripts/{date}_{video_id}.json: Raw transcript and metadata

Usage:
    echo '{"video_id": "...", "metadata": {...}, "transcript": {...}, "analysis": "..."}' | \
        uv run save_analysis.py --mode wisdom --tags "ai,coding"

Environment:
    CLAUDE_KNOWLEDGE_DIR: Knowledge base directory (default: ~/.claude/knowledge)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import yaml


class Metadata(TypedDict, total=False):
    title: str
    channel: str
    description: str
    duration_seconds: int
    duration_formatted: str
    view_count: int
    upload_date: str
    tags: list[str]


class Transcript(TypedDict, total=False):
    text: str
    language: str
    segments: list[dict]


class AnalysisInput(TypedDict, total=False):
    video_id: str
    metadata: Metadata
    transcript: Transcript
    errors: list[str]
    analysis: str


def get_knowledge_dir() -> Path:
    """Get the knowledge base directory from env or default."""
    default = Path.home() / ".claude" / "knowledge"
    env_dir = os.environ.get("CLAUDE_KNOWLEDGE_DIR")
    return Path(env_dir) if env_dir else default


def ensure_dirs(knowledge_dir: Path) -> Path:
    """Create knowledge directory structure if needed."""
    youtube_dir = knowledge_dir / "youtube"
    (youtube_dir / "analyses").mkdir(parents=True, exist_ok=True)
    (youtube_dir / "transcripts").mkdir(parents=True, exist_ok=True)

    # Ensure transcripts are gitignored
    gitignore = youtube_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("# Raw transcripts are large and can be re-fetched\ntranscripts/\n")

    return youtube_dir


def generate_filename(video_id: str, date: datetime) -> str:
    """Generate analysis filename."""
    date_str = date.strftime("%Y-%m-%d")
    return f"{date_str}_{video_id}.md"


def build_frontmatter(
    video_id: str,
    metadata: Metadata,
    mode: str,
    tags: list[str],
    analyzed: datetime,
) -> dict:
    """Build YAML frontmatter for the analysis file."""
    return {
        "video_id": video_id,
        "url": f"https://youtube.com/watch?v={video_id}",
        "title": metadata.get("title", "Unknown"),
        "channel": metadata.get("channel", "Unknown"),
        "duration": metadata.get("duration_formatted", ""),
        "analyzed": analyzed.isoformat(),
        "analysis_mode": mode,
        "tags": tags,
    }


def build_markdown(
    frontmatter: dict,
    metadata: Metadata,
    analysis: str,
    analyzed: datetime,
) -> str:
    """Build the full markdown content."""
    yaml_block = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)

    header = f"""---
{yaml_block.strip()}
---

# {metadata.get('title', 'Unknown')}

**Channel**: {metadata.get('channel', 'Unknown')}
**Duration**: {metadata.get('duration_formatted', 'Unknown')}
**Analyzed**: {analyzed.strftime('%Y-%m-%d')}

"""

    return header + analysis


def update_index(youtube_dir: Path, frontmatter: dict, filename: str) -> None:
    """Update or create the index.md file."""
    index_path = youtube_dir / "index.md"

    # Build new row
    date = frontmatter["analyzed"][:10]
    title = frontmatter["title"]
    channel = frontmatter["channel"]
    mode = frontmatter["analysis_mode"]
    link = f"[{title}](analyses/{filename})"

    new_row = f"| {date} | {link} | {channel} | {mode} |"

    if index_path.exists():
        content = index_path.read_text()
        lines = content.split("\n")

        # Find the table and insert after header
        table_start = None
        for i, line in enumerate(lines):
            if line.startswith("| Date |"):
                table_start = i + 2  # Skip header and separator
                break

        if table_start is not None:
            lines.insert(table_start, new_row)
            content = "\n".join(lines)
        else:
            # No table found, append one
            content += f"\n\n| Date | Title | Channel | Mode |\n|------|-------|---------|------|\n{new_row}\n"
    else:
        content = f"""# YouTube Knowledge Base

Analyzed videos from the youtube-content skill.

| Date | Title | Channel | Mode |
|------|-------|---------|------|
{new_row}
"""

    index_path.write_text(content)


def save_transcript(
    youtube_dir: Path,
    video_id: str,
    metadata: Metadata,
    transcript: Transcript | None,
    errors: list[str],
    analyzed: datetime,
) -> Path:
    """Save raw transcript data as JSON."""
    filename = generate_filename(video_id, analyzed).replace(".md", ".json")
    filepath = youtube_dir / "transcripts" / filename

    data = {
        "video_id": video_id,
        "metadata": metadata,
        "transcript": transcript,
        "errors": errors,
        "fetched": analyzed.isoformat(),
    }

    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return filepath


def save_analysis(
    data: AnalysisInput,
    mode: str,
    tags: list[str],
) -> tuple[Path, Path]:
    """Save analysis and transcript to knowledge base and return file paths."""
    video_id = data.get("video_id", "unknown")
    metadata = data.get("metadata", {})
    transcript = data.get("transcript")
    errors = data.get("errors", [])
    analysis = data.get("analysis", "")

    knowledge_dir = get_knowledge_dir()
    youtube_dir = ensure_dirs(knowledge_dir)

    analyzed = datetime.now(timezone.utc)
    filename = generate_filename(video_id, analyzed)
    analysis_path = youtube_dir / "analyses" / filename

    # Save analysis
    frontmatter = build_frontmatter(video_id, metadata, mode, tags, analyzed)
    content = build_markdown(frontmatter, metadata, analysis, analyzed)
    analysis_path.write_text(content)
    update_index(youtube_dir, frontmatter, filename)

    # Save raw transcript
    transcript_path = save_transcript(
        youtube_dir, video_id, metadata, transcript, errors, analyzed
    )

    return analysis_path, transcript_path


def main():
    parser = argparse.ArgumentParser(description="Save analysis to knowledge base")
    parser.add_argument(
        "--mode",
        default="summary",
        help="Analysis mode (wisdom, summary, qa, quotes, custom)",
    )
    parser.add_argument(
        "--tags",
        default="",
        help="Comma-separated tags",
    )
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    # Read JSON from stdin
    try:
        data: AnalysisInput = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(1)

    if "video_id" not in data:
        print(json.dumps({"error": "Missing video_id in input"}))
        sys.exit(1)

    analysis_path, transcript_path = save_analysis(data, args.mode, tags)

    print(json.dumps({
        "saved": True,
        "analysis_path": str(analysis_path),
        "transcript_path": str(transcript_path),
        "knowledge_dir": str(get_knowledge_dir()),
    }))


if __name__ == "__main__":
    main()
