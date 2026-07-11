#!/usr/bin/env python3
"""Resolve skill source and clone locally for inspection."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

EVAL_DIR = Path("/tmp/skill-eval")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def resolve_github_url(source: str) -> str | None:
    """Resolve source to a GitHub clone URL."""
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https") and "github.com" in parsed.netloc:
        return source
    # skills.sh identifier: owner/repo or owner/repo/path
    parts = source.strip("/").split("/")
    if len(parts) >= 2 and not parsed.scheme:
        return f"https://github.com/{parts[0]}/{parts[1]}"
    return None


def find_skill_md(base: Path, skill_name: str | None) -> Path | None:
    """Locate SKILL.md within a repo, optionally filtering by skill name."""
    candidates = sorted(base.rglob("SKILL.md"))
    if not candidates:
        return None
    if skill_name:
        for c in candidates:
            if skill_name in str(c.parent):
                return c
    return candidates[0]


def get_repo_metadata(url: str) -> dict:
    """Fetch repo metadata via gh CLI."""
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        return {}
    repo = f"{parts[0]}/{parts[1]}"
    result = run([
        "gh", "repo", "view", repo, "--json",
        "stargazerCount,forkCount,licenseInfo,pushedAt,description,name,owner"
    ])
    if result.returncode != 0:
        return {"error": result.stderr.strip()}
    try:
        data = json.loads(result.stdout)
        return {
            "stars": data.get("stargazerCount", 0),
            "forks": data.get("forkCount", 0),
            "license": (data.get("licenseInfo") or {}).get("key", "unknown"),
            "last_updated": data.get("pushedAt", "unknown"),
            "description": data.get("description", ""),
            "owner": (data.get("owner") or {}).get("login", "unknown"),
            "name": data.get("name", ""),
        }
    except json.JSONDecodeError:
        return {"error": "Failed to parse gh output"}


def clone_repo(url: str, name: str) -> Path:
    """Shallow clone a repo to eval directory."""
    dest = EVAL_DIR / name
    if dest.exists():
        import shutil
        shutil.rmtree(dest)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    result = run(["git", "clone", "--depth", "1", url, str(dest)])
    if result.returncode != 0:
        print(f"Error cloning: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return dest


def list_files(path: Path) -> list[dict]:
    """List all files with relative paths and sizes."""
    files = []
    for f in sorted(path.rglob("*")):
        if f.is_file() and ".git" not in f.parts:
            files.append({
                "path": str(f.relative_to(path)),
                "size": f.stat().st_size,
            })
    return files


def main():
    parser = argparse.ArgumentParser(description="Fetch skill for evaluation")
    parser.add_argument("--source", required=True, help="GitHub URL, skills.sh ID, or local path")
    parser.add_argument("--skill", help="Skill name (for multi-skill repos)")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    source = args.source
    local_path = Path(source).expanduser()

    if local_path.exists():
        skill_md = find_skill_md(local_path, args.skill)
        result = {
            "skill_path": str(skill_md.parent) if skill_md else str(local_path),
            "source_type": "local",
            "repo_metadata": {},
            "files": list_files(skill_md.parent if skill_md else local_path),
            "skill_md_found": skill_md is not None,
        }
    else:
        url = resolve_github_url(source)
        if not url:
            print(json.dumps({"error": f"Cannot resolve source: {source}"}))
            sys.exit(1)

        # Derive name from URL or skill arg
        parts = urlparse(url).path.strip("/").split("/")
        name = args.skill or parts[-1] if parts else "unknown"

        repo_path = clone_repo(url, name)
        metadata = get_repo_metadata(url)
        skill_md = find_skill_md(repo_path, args.skill)
        skill_dir = skill_md.parent if skill_md else repo_path

        result = {
            "skill_path": str(skill_dir),
            "source_type": "github",
            "repo_metadata": metadata,
            "files": list_files(skill_dir),
            "skill_md_found": skill_md is not None,
            "clone_path": str(repo_path),
        }

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"Skill path: {result['skill_path']}")
        print(f"Source: {result['source_type']}")
        if result.get("repo_metadata"):
            m = result["repo_metadata"]
            print(f"Stars: {m.get('stars', '?')} | Forks: {m.get('forks', '?')} | License: {m.get('license', '?')}")
        print(f"Files: {len(result['files'])}")
        for f in result["files"]:
            print(f"  {f['path']} ({f['size']} bytes)")


if __name__ == "__main__":
    main()
