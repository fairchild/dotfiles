#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check image-gen provider scripts against the adapter protocol.

Usage:
  scripts/check_protocol.py
  scripts/check_protocol.py --provider openai
  scripts/check_protocol.py --json

The check is intentionally free: it calls provider scripts with --protocol,
which must not require provider SDK imports, credentials, or paid generation.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_NAME = "check_protocol.py"
PROTOCOL_VERSION = "image-gen-provider/v1"
REQUIRED_OPTIONS = (
    "--prompt",
    "--output",
    "--output-dir",
    "--model",
    "--check",
    "--protocol",
)
REQUIRED_FUNCTIONS = ("check_config", "generate_image", "print_protocol", "main")
REQUIRED_PROTOCOL_KEYS = (
    "protocol_version",
    "provider",
    "default_model",
    "required_options",
    "final_stdout",
    "history",
    "local_helper_imports",
    "supports",
)
ALLOWED_LOCAL_IMPORTS = {"common"}

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {"env": ("OPENAI_API_KEY",), "script": "generate_openai.py", "ext": ".png"},
    "imagen": {
        "env": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        "script": "generate_imagen.py",
        "ext": ".png",
    },
    "gemini": {
        "env": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        "script": "generate_gemini.py",
        "ext": ".png",
    },
    "fal": {"env": ("FAL_KEY",), "script": "generate_fal.py", "ext": ".jpg"},
}


@dataclass(frozen=True)
class ProviderProtocolResult:
    provider: str
    script: str
    problems: tuple[str, ...]
    protocol: dict[str, Any]

    @property
    def ok(self) -> bool:
        return not self.problems


def check_provider_protocols(
    providers: list[str] | None = None,
    scripts_dir: Path = SCRIPTS_DIR,
    python: str = sys.executable,
) -> list[ProviderProtocolResult]:
    selected = providers or list(PROVIDERS.keys())
    unknown = sorted(set(selected) - set(PROVIDERS))
    if unknown:
        raise ValueError(f"unknown provider(s): {', '.join(unknown)}")
    return [check_provider_protocol(provider, scripts_dir, python) for provider in selected]


def check_provider_protocol(
    provider: str,
    scripts_dir: Path = SCRIPTS_DIR,
    python: str = sys.executable,
) -> ProviderProtocolResult:
    config = PROVIDERS[provider]
    script_name = str(config["script"])
    path = scripts_dir / script_name
    problems: list[str] = []
    protocol: dict[str, Any] = {}

    if not path.exists():
        return ProviderProtocolResult(provider, script_name, ("script missing",), protocol)

    text = path.read_text()
    if not text.startswith("#!/usr/bin/env -S uv run --script"):
        problems.append("missing executable uv shebang")
    if not has_pep_723_metadata(text):
        problems.append("missing PEP 723 script metadata")
    if not os.access(path, os.X_OK):
        problems.append("script is not executable")

    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return ProviderProtocolResult(
            provider,
            script_name,
            tuple(problems + [f"parse failed: {error}"]),
            protocol,
        )

    try:
        compile(text, str(path), "exec")
    except SyntaxError as error:
        problems.append(f"compile failed: {error}")

    options = argparse_options(tree)
    functions = top_level_functions(tree)
    local_imports = local_script_imports(tree, scripts_dir)
    protocol = provider_protocol(path, python)

    missing_options = [option for option in REQUIRED_OPTIONS if option not in options]
    if missing_options:
        problems.append(f"missing options: {', '.join(missing_options)}")

    missing_functions = [name for name in REQUIRED_FUNCTIONS if name not in functions]
    if missing_functions:
        problems.append(f"missing functions: {', '.join(missing_functions)}")

    disallowed_imports = sorted(local_imports - ALLOWED_LOCAL_IMPORTS)
    if disallowed_imports:
        problems.append(f"disallowed local imports: {', '.join(disallowed_imports)}")

    problems.extend(validate_protocol_payload(provider, protocol))

    if "record_generation(" not in text:
        problems.append("does not record successful generations")
    if "print(output_path.resolve())" not in text:
        problems.append("does not print resolved output path as final success line")

    return ProviderProtocolResult(provider, script_name, tuple(problems), protocol)


def has_pep_723_metadata(text: str) -> bool:
    return "# /// script" in text and "# ///" in text and "requires-python" in text


def provider_protocol(path: Path, python: str = sys.executable) -> dict[str, Any]:
    result = subprocess.run(
        [python, str(path), "--protocol"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode != 0:
        return {"_error": result.stderr.strip() or result.stdout.strip() or "unknown error"}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        return {"_error": f"invalid JSON: {error}"}


def validate_protocol_payload(provider: str, protocol: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if protocol.get("_error"):
        return [f"--protocol failed: {protocol['_error']}"]

    missing_keys = [key for key in REQUIRED_PROTOCOL_KEYS if key not in protocol]
    if missing_keys:
        problems.append(f"protocol missing keys: {', '.join(missing_keys)}")

    if protocol.get("protocol_version") != PROTOCOL_VERSION:
        problems.append(f"protocol_version is not {PROTOCOL_VERSION}")
    if protocol.get("provider") != provider:
        problems.append(f"protocol provider is {protocol.get('provider')!r}")
    if not protocol.get("default_model"):
        problems.append("protocol default_model is missing")
    if protocol.get("final_stdout") != "resolved_output_path":
        problems.append("protocol final_stdout must be resolved_output_path")
    if protocol.get("history") != "generations.jsonl":
        problems.append("protocol history must be generations.jsonl")

    protocol_options = set(protocol.get("required_options") or [])
    missing_protocol_options = [
        option for option in REQUIRED_OPTIONS if option not in protocol_options
    ]
    if missing_protocol_options:
        problems.append(
            "protocol missing required_options: " + ", ".join(missing_protocol_options)
        )

    protocol_imports = set(protocol.get("local_helper_imports") or [])
    disallowed_protocol_imports = sorted(protocol_imports - ALLOWED_LOCAL_IMPORTS)
    if disallowed_protocol_imports:
        problems.append(
            "protocol disallowed local_helper_imports: "
            + ", ".join(disallowed_protocol_imports)
        )

    supports = protocol.get("supports")
    if not isinstance(supports, dict) or not supports:
        problems.append("protocol supports must be a non-empty object")

    return problems


def argparse_options(tree: ast.AST) -> set[str]:
    options: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if arg.value.startswith("--"):
                    options.add(arg.value)
    return options


def top_level_functions(tree: ast.AST) -> set[str]:
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def local_script_imports(tree: ast.AST, scripts_dir: Path = SCRIPTS_DIR) -> set[str]:
    local_modules = {path.stem for path in scripts_dir.glob("*.py")}
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in local_modules:
                    imports.add(root)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".", 1)[0]
            if root in local_modules:
                imports.add(root)
    return imports


def failure_count(results: list[ProviderProtocolResult]) -> int:
    return sum(1 for result in results if not result.ok)


def print_protocol_report(results: list[ProviderProtocolResult]) -> None:
    print("=== Image-Gen Provider Protocol Check ===")
    for result in results:
        if result.ok:
            print(f"  {result.provider}: protocol OK")
        else:
            print(f"  {result.provider}: failed ({'; '.join(result.problems)})")


def result_payload(result: ProviderProtocolResult) -> dict[str, Any]:
    return {
        "provider": result.provider,
        "script": result.script,
        "ok": result.ok,
        "problems": list(result.problems),
        "protocol": result.protocol,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check image-gen provider protocol")
    parser.add_argument("--provider", choices=sorted(PROVIDERS), help="Check one provider")
    parser.add_argument("--json", action="store_true", help="Print machine-readable results")
    parser.add_argument(
        "--scripts-dir",
        type=Path,
        default=SCRIPTS_DIR,
        help="Provider scripts directory",
    )
    args = parser.parse_args()

    providers = [args.provider] if args.provider else None
    results = check_provider_protocols(providers=providers, scripts_dir=args.scripts_dir)
    if args.json:
        print(json.dumps([result_payload(result) for result in results], indent=2))
    else:
        print_protocol_report(results)
    sys.exit(1 if failure_count(results) else 0)


if __name__ == "__main__":
    main()
