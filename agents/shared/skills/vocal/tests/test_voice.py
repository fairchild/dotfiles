#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Vocal skill test suite.

Usage:
  uv run tests/test_voice.py                # Run --check for each provider
  uv run tests/test_voice.py --generate     # Run generation/transcription tests
  uv run tests/test_voice.py --provider local-tts

Exit codes: 0 = all pass, 1 = one or more failures
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROVIDERS = {
    "local-tts": {"env": None, "script": "tts_local.py", "kind": "tts", "ext": ".aiff"},
    "local-stt": {"env": None, "script": "stt_local.py", "kind": "stt", "ext": None},
    "elevenlabs-tts": {
        "env": ("ELEVENLABS_API_KEY", "ELEVEN_LABS_API_KEY"),
        "script": "tts_elevenlabs.py",
        "kind": "tts",
        "ext": ".mp3",
    },
    "elevenlabs-stt": {
        "env": ("ELEVENLABS_API_KEY", "ELEVEN_LABS_API_KEY"),
        "script": "stt_elevenlabs.py",
        "kind": "stt",
        "ext": None,
    },
}

SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
TEST_TEXT = "Vocal skill test."


def env_is_set(provider: str) -> bool:
    env_var = PROVIDERS[provider]["env"]
    if env_var is None:
        return True
    if isinstance(env_var, tuple):
        return any(bool(os.environ.get(name)) for name in env_var)
    return bool(os.environ.get(env_var))


def run_check(provider: str) -> tuple[bool, str]:
    script = SCRIPTS_DIR / PROVIDERS[provider]["script"]
    if not env_is_set(provider):
        env_var = PROVIDERS[provider]["env"]
        return False, f"missing {env_var!r}"

    try:
        result = subprocess.run(
            ["uv", "run", str(script), "--check"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout (120s)"
    except Exception as exc:
        return False, str(exc)

    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip() or "unknown error"
        return False, msg

    msg = result.stdout.strip() or "ok"
    return True, msg


def run_generate(provider: str, temp_dir: Path) -> tuple[bool, str]:
    script = SCRIPTS_DIR / PROVIDERS[provider]["script"]
    if not env_is_set(provider):
        env_var = PROVIDERS[provider]["env"]
        return False, f"missing {env_var!r}"

    kind = PROVIDERS[provider]["kind"]
    cmd = ["uv", "run", str(script)]

    if kind == "tts":
        ext = PROVIDERS[provider]["ext"]
        output = temp_dir / f"{provider}{ext}"
        cmd.extend(["--text", TEST_TEXT, "--output", str(output)])
    else:
        cmd.extend(["--duration", "2"])
        output = None

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout (600s)"
    except Exception as exc:
        return False, str(exc)

    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip() or "unknown error"
        return False, msg

    if kind == "tts":
        assert output is not None
        if not output.exists() or output.stat().st_size == 0:
            return False, "output file missing or empty"
        return True, f"wrote {output.stat().st_size} bytes"

    transcript = result.stdout.strip()
    if not transcript:
        return False, "empty transcript"
    return True, f"transcript: {transcript[:60]}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Test vocal skill")
    parser.add_argument("--generate", "-g", action="store_true", help="Run generation and transcription tests")
    parser.add_argument("--provider", "-p", choices=list(PROVIDERS.keys()), help="Run only one provider")
    args = parser.parse_args()

    providers = [args.provider] if args.provider else list(PROVIDERS.keys())
    failures = 0

    print("=== Provider Check ===")
    for provider in providers:
        ok, msg = run_check(provider)
        status = "PASS" if ok else "FAIL"
        print(f"  {provider}: {status} {msg}")
        if not ok:
            failures += 1

    if args.generate:
        print("\n=== Generate/Test Run ===")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for provider in providers:
                ok, msg = run_generate(provider, tmp_dir)
                status = "PASS" if ok else "FAIL"
                print(f"  {provider}: {status} {msg}")
                if not ok:
                    failures += 1

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
