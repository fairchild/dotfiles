#!/usr/bin/env python3
"""Token cost estimation for skill adoption."""

import argparse
import json
import sys
from pathlib import Path

METADATA_WORD_GUIDELINE = 100
BODY_WORD_GUIDELINE = 500
LIGHT_THRESHOLD = 2000
HEAVY_THRESHOLD = 10000

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".sh", ".bash", ".zsh", ".md", ".yaml", ".yml",
    ".toml", ".json", ".txt", ".html", ".css", ".rb", ".go", ".rs", ".swift",
}


def estimate_tokens(text: str) -> int:
    """Conservative token estimate: ~4 chars per token for English."""
    return len(text) // 4


def word_count(text: str) -> int:
    return len(text.split())


def analyze_skill_md(skill_md: Path) -> dict:
    """Break down SKILL.md into metadata and body."""
    content = skill_md.read_text()
    metadata_text = ""
    body_text = content

    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            metadata_text = content[3:end].strip()
            body_text = content[end + 3:].strip()

    return {
        "metadata": {
            "words": word_count(metadata_text),
            "tokens": estimate_tokens(metadata_text),
            "guideline": METADATA_WORD_GUIDELINE,
            "over_guideline": word_count(metadata_text) > METADATA_WORD_GUIDELINE,
        },
        "body": {
            "words": word_count(body_text),
            "lines": len(body_text.splitlines()),
            "tokens": estimate_tokens(body_text),
            "guideline": BODY_WORD_GUIDELINE,
            "over_guideline": word_count(body_text) > BODY_WORD_GUIDELINE,
        },
    }


def analyze_references(refs_dir: Path) -> list[dict]:
    """Analyze each reference file."""
    if not refs_dir.exists():
        return []
    results = []
    for f in sorted(refs_dir.rglob("*")):
        if f.is_file() and f.suffix in TEXT_EXTENSIONS:
            text = f.read_text(errors="replace")
            results.append({
                "file": str(f.relative_to(refs_dir.parent)),
                "words": word_count(text),
                "tokens": estimate_tokens(text),
            })
    return results


def analyze_scripts(scripts_dir: Path) -> dict:
    """Count and size script files."""
    if not scripts_dir.exists():
        return {"count": 0, "total_bytes": 0, "files": []}
    files = []
    total = 0
    for f in sorted(scripts_dir.rglob("*")):
        if f.is_file():
            size = f.stat().st_size
            total += size
            files.append({"file": str(f.relative_to(scripts_dir.parent)), "bytes": size})
    return {"count": len(files), "total_bytes": total, "files": files}


def main():
    parser = argparse.ArgumentParser(description="Context budget analysis for skills")
    parser.add_argument("--path", required=True, help="Skill directory to analyze")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    skill_path = Path(args.path)
    if not skill_path.exists():
        print(f"Error: {skill_path} does not exist", file=sys.stderr)
        sys.exit(1)

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"Error: No SKILL.md found in {skill_path}", file=sys.stderr)
        sys.exit(1)

    md_analysis = analyze_skill_md(skill_md)
    references = analyze_references(skill_path / "references")
    scripts = analyze_scripts(skill_path / "scripts")

    refs_total_tokens = sum(r["tokens"] for r in references)
    triggered_tokens = md_analysis["metadata"]["tokens"] + md_analysis["body"]["tokens"]
    total_all_loaded = triggered_tokens + refs_total_tokens

    if triggered_tokens < LIGHT_THRESHOLD:
        assessment = "Light"
    elif triggered_tokens < HEAVY_THRESHOLD:
        assessment = "Moderate"
    else:
        assessment = "Heavy"

    result = {
        "skill_md": md_analysis,
        "references": references,
        "references_total_tokens": refs_total_tokens,
        "scripts": scripts,
        "triggered_tokens": triggered_tokens,
        "total_if_all_loaded": total_all_loaded,
        "assessment": assessment,
        "thresholds": {
            "light": f"<{LIGHT_THRESHOLD}",
            "moderate": f"{LIGHT_THRESHOLD}-{HEAVY_THRESHOLD}",
            "heavy": f">{HEAVY_THRESHOLD}",
        },
    }

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"Context Budget Analysis")
        print(f"=======================")
        print(f"\nSKILL.md Metadata: {md_analysis['metadata']['words']} words, ~{md_analysis['metadata']['tokens']} tokens")
        print(f"  Guideline: {METADATA_WORD_GUIDELINE} words {'(OVER)' if md_analysis['metadata']['over_guideline'] else '(OK)'}")
        print(f"\nSKILL.md Body: {md_analysis['body']['words']} words, {md_analysis['body']['lines']} lines, ~{md_analysis['body']['tokens']} tokens")
        print(f"  Guideline: {BODY_WORD_GUIDELINE} words {'(OVER)' if md_analysis['body']['over_guideline'] else '(OK)'}")
        print(f"\nReferences ({len(references)} files):")
        for r in references:
            print(f"  {r['file']}: {r['words']} words, ~{r['tokens']} tokens")
        print(f"  Total: ~{refs_total_tokens} tokens")
        print(f"\nScripts: {scripts['count']} files, {scripts['total_bytes']} bytes")
        print(f"\nTriggered tokens (metadata + body): ~{triggered_tokens}")
        print(f"Total if all loaded: ~{total_all_loaded}")
        print(f"\nAssessment: {assessment} ({result['thresholds'][assessment.lower()]} triggered tokens)")


if __name__ == "__main__":
    main()
