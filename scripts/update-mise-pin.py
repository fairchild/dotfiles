#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Update only the mise tables in install/pins.toml."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import re
import tomllib


TABLE_RE = re.compile(r"^\s*\[([^]]+)]\s*(?:#.*)?$")
VERSION_RE = re.compile(r"^v\d{4}\.\d+\.\d+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def replace_table_value(
    lines: list[str], table: str, key_token: str, value: str
) -> None:
    current_table = ""
    matches: list[tuple[int, re.Match[str]]] = []
    key_re = re.compile(rf"^(\s*{re.escape(key_token)}\s*=\s*).*$")

    for index, line in enumerate(lines):
        table_match = TABLE_RE.match(line.rstrip("\n"))
        if table_match:
            current_table = table_match.group(1)
            continue
        if current_table == table:
            key_match = key_re.match(line.rstrip("\n"))
            if key_match:
                matches.append((index, key_match))

    if len(matches) != 1:
        raise ValueError(f"expected exactly one {table}.{key_token}, found {len(matches)}")

    index, match = matches[0]
    lines[index] = f"{match.group(1)}{json.dumps(value)}\n"


def rewrite_pin(
    source: str,
    *,
    version: str,
    released_at: str,
    shas: dict[str, str],
) -> str:
    if not VERSION_RE.fullmatch(version):
        raise ValueError(f"invalid mise version: {version}")
    try:
        dt.datetime.fromisoformat(released_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid release timestamp: {released_at}") from exc

    platforms = ("linux-x64", "linux-arm64", "macos-x64", "macos-arm64")
    if set(shas) != set(platforms):
        raise ValueError("mise SHA map must contain exactly the four supported platforms")
    for platform, digest in shas.items():
        if not SHA256_RE.fullmatch(digest):
            raise ValueError(f"invalid SHA-256 for {platform}")

    before = tomllib.loads(source)
    lines = source.splitlines(keepends=True)
    replacements = {
        ("mise", "version"): version,
        ("mise", "released_at"): released_at,
        ("mise", "release_url"): f"https://github.com/jdx/mise/releases/tag/{version}",
        (
            "mise",
            "shasums_url",
        ): f"https://github.com/jdx/mise/releases/download/{version}/SHASUMS256.asc",
    }
    for (table, key), value in replacements.items():
        replace_table_value(lines, table, key, value)
    for platform in platforms:
        replace_table_value(lines, "mise.sha256", json.dumps(platform), shas[platform])

    rewritten = "".join(lines)
    after = tomllib.loads(rewritten)
    expected = copy.deepcopy(before)
    expected_mise = expected.get("mise")
    if not isinstance(expected_mise, dict) or not isinstance(
        expected_mise.get("sha256"), dict
    ):
        raise ValueError("pins file lacks required mise tables")
    expected_mise.update(
        version=version,
        released_at=released_at,
        release_url=replacements[("mise", "release_url")],
        shasums_url=replacements[("mise", "shasums_url")],
    )
    expected_mise["sha256"].update(shas)
    if after != expected:
        raise ValueError("rewrite changed data outside the approved mise fields")
    return rewritten


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--file", type=Path, default=Path("install/pins.toml"))
    result.add_argument("--version", required=True)
    result.add_argument("--released-at", required=True)
    for platform in ("linux-x64", "linux-arm64", "macos-x64", "macos-arm64"):
        result.add_argument(f"--{platform}", required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    source = args.file.read_text(encoding="utf-8")
    shas = {
        "linux-x64": args.linux_x64,
        "linux-arm64": args.linux_arm64,
        "macos-x64": args.macos_x64,
        "macos-arm64": args.macos_arm64,
    }
    rewritten = rewrite_pin(
        source, version=args.version, released_at=args.released_at, shas=shas
    )
    args.file.write_text(rewritten, encoding="utf-8")
    print(f"Updated only mise pins in {args.file} for {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
