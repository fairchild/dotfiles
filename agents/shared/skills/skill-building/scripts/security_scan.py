#!/usr/bin/env python3
"""Static security pattern analysis for skill files."""

import argparse
import json
import re
import sys
from pathlib import Path

PATTERNS: dict[str, list[dict]] = {
    "filesystem": [
        {"pattern": r"rm\s+-rf", "severity": "HIGH", "desc": "Recursive file deletion"},
        {"pattern": r"shutil\.rmtree", "severity": "HIGH", "desc": "Directory tree removal"},
        {"pattern": r"\.\./", "severity": "MEDIUM", "desc": "Path traversal"},
        {"pattern": r"chmod\s", "severity": "MEDIUM", "desc": "Permission modification"},
        {"pattern": r"os\.remove|os\.unlink", "severity": "MEDIUM", "desc": "File deletion"},
        {"pattern": r"open\(.*['\"][wa][+]?['\"]", "severity": "LOW", "desc": "File write operation"},
    ],
    "network": [
        {"pattern": r"requests\.(post|put|patch|delete)", "severity": "CRITICAL", "desc": "Outbound HTTP mutation"},
        {"pattern": r"requests\.get", "severity": "MEDIUM", "desc": "Outbound HTTP read"},
        {"pattern": r"urllib\.request\.(urlopen|urlretrieve)", "severity": "HIGH", "desc": "URL fetch"},
        {"pattern": r"\bcurl\b", "severity": "MEDIUM", "desc": "curl command"},
        {"pattern": r"\bwget\b", "severity": "MEDIUM", "desc": "wget command"},
        {"pattern": r"https?://[^\s\"')\]]+", "severity": "LOW", "desc": "Hardcoded URL"},
        {"pattern": r"fetch\(", "severity": "MEDIUM", "desc": "Fetch API call"},
    ],
    "credentials": [
        {"pattern": r"os\.environ", "severity": "HIGH", "desc": "Environment variable access"},
        {"pattern": r"process\.env", "severity": "HIGH", "desc": "Node env access"},
        {"pattern": r"~/\.ssh|\.ssh/", "severity": "CRITICAL", "desc": "SSH key access"},
        {"pattern": r"\.env\b", "severity": "HIGH", "desc": "Dotenv file reference"},
        {"pattern": r"(?i)(keychain|token|secret|password|api_key|apikey)", "severity": "MEDIUM", "desc": "Credential keyword"},
    ],
    "code_execution": [
        {"pattern": r"\beval\s*\(", "severity": "CRITICAL", "desc": "Dynamic eval"},
        {"pattern": r"\bexec\s*\(", "severity": "CRITICAL", "desc": "Dynamic exec"},
        {"pattern": r"subprocess\.(run|call|Popen|check_output)", "severity": "HIGH", "desc": "Subprocess execution"},
        {"pattern": r"os\.system\s*\(", "severity": "CRITICAL", "desc": "OS system call"},
        {"pattern": r"__import__\s*\(", "severity": "HIGH", "desc": "Dynamic import"},
        {"pattern": r"importlib\.import_module", "severity": "HIGH", "desc": "Dynamic module import"},
        {"pattern": r"child_process", "severity": "HIGH", "desc": "Node child process"},
    ],
    "persistence": [
        {"pattern": r"hooks:", "severity": "MEDIUM", "desc": "Hook definition (auto-running code)"},
        {"pattern": r"crontab", "severity": "HIGH", "desc": "Cron job manipulation"},
        {"pattern": r"launchctl", "severity": "HIGH", "desc": "macOS launch agent"},
        {"pattern": r"LaunchAgents|LaunchDaemons", "severity": "HIGH", "desc": "Startup directory reference"},
        {"pattern": r"systemctl|systemd", "severity": "HIGH", "desc": "Systemd service manipulation"},
    ],
    "obfuscation": [
        {"pattern": r"[A-Za-z0-9+/=]{100,}", "severity": "CRITICAL", "desc": "Long base64-like string"},
        {"pattern": r"\\x[0-9a-fA-F]{2}(\\x[0-9a-fA-F]{2}){9,}", "severity": "CRITICAL", "desc": "Hex-encoded string sequence"},
        {"pattern": r'(\+\s*["\'][^"\']{1,3}["\']){5,}', "severity": "HIGH", "desc": "String concatenation assembly"},
        {"pattern": r"atob\(|btoa\(|base64\.(b64decode|decodebytes)", "severity": "HIGH", "desc": "Base64 decode operation"},
    ],
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".sh", ".bash", ".zsh", ".md", ".yaml", ".yml",
    ".toml", ".json", ".txt", ".html", ".css", ".rb", ".go", ".rs", ".swift",
}


def scan_file(filepath: Path, base_path: Path) -> list[dict]:
    """Scan a single file for security patterns."""
    findings = []
    if filepath.suffix not in TEXT_EXTENSIONS:
        return findings
    try:
        content = filepath.read_text(errors="replace")
    except (OSError, UnicodeDecodeError):
        return findings

    lines = content.splitlines()
    rel_path = str(filepath.relative_to(base_path))

    for category, patterns in PATTERNS.items():
        for pat in patterns:
            regex = re.compile(pat["pattern"])
            for i, line in enumerate(lines, 1):
                if regex.search(line):
                    findings.append({
                        "category": category,
                        "severity": pat["severity"],
                        "description": pat["desc"],
                        "file": rel_path,
                        "line": i,
                        "context": line.strip()[:200],
                    })
    return findings


def scan_frontmatter(skill_md: Path) -> list[dict]:
    """Check frontmatter for capability-expanding fields."""
    findings = []
    try:
        content = skill_md.read_text()
    except (OSError, UnicodeDecodeError):
        return findings

    if not content.startswith("---"):
        return findings

    end = content.find("---", 3)
    if end == -1:
        return findings
    frontmatter = content[3:end]

    if re.search(r"^hooks:", frontmatter, re.MULTILINE):
        findings.append({
            "category": "persistence",
            "severity": "MEDIUM",
            "description": "Frontmatter hooks (auto-running code on tool use)",
            "file": "SKILL.md",
            "line": 0,
            "context": "hooks: defined in frontmatter",
        })
    if re.search(r"^allowed-tools:", frontmatter, re.MULTILINE):
        findings.append({
            "category": "credentials",
            "severity": "MEDIUM",
            "description": "Frontmatter allowed-tools (capability expansion)",
            "file": "SKILL.md",
            "line": 0,
            "context": "allowed-tools: defined in frontmatter",
        })
    return findings


def summarize(findings: list[dict]) -> dict:
    """Produce severity counts and verdict."""
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    categories_hit = set()
    for f in findings:
        counts[f["severity"]] += 1
        categories_hit.add(f["category"])

    if counts["CRITICAL"] > 0:
        verdict = "FAIL"
    elif counts["HIGH"] > 3:
        verdict = "FAIL"
    elif counts["HIGH"] > 0:
        verdict = "WARN"
    elif counts["MEDIUM"] > 5:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return {
        "verdict": verdict,
        "counts": counts,
        "categories": sorted(categories_hit),
        "total_findings": len(findings),
    }


def main():
    parser = argparse.ArgumentParser(description="Security scan for skill files")
    parser.add_argument("--path", required=True, help="Skill directory to scan")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    skill_path = Path(args.path)
    if not skill_path.exists():
        print(f"Error: {skill_path} does not exist", file=sys.stderr)
        sys.exit(1)

    findings: list[dict] = []

    # Scan all files
    for f in sorted(skill_path.rglob("*")):
        if f.is_file() and ".git" not in f.parts:
            findings.extend(scan_file(f, skill_path))

    # Check frontmatter
    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        findings.extend(scan_frontmatter(skill_md))

    summary = summarize(findings)

    if args.format == "json":
        print(json.dumps({"summary": summary, "findings": findings}, indent=2))
    else:
        print(f"Security Verdict: {summary['verdict']}")
        print(f"Total findings: {summary['total_findings']}")
        print(f"  CRITICAL: {summary['counts']['CRITICAL']}")
        print(f"  HIGH:     {summary['counts']['HIGH']}")
        print(f"  MEDIUM:   {summary['counts']['MEDIUM']}")
        print(f"  LOW:      {summary['counts']['LOW']}")
        print(f"Categories: {', '.join(summary['categories'])}")
        if findings:
            print("\nFindings:")
            for f in findings:
                print(f"  [{f['severity']}] {f['file']}:{f['line']} - {f['description']}")
                print(f"    {f['context']}")


if __name__ == "__main__":
    main()
