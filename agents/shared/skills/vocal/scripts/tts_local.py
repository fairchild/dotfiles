#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Speak text with macOS say."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def error_exit(msg: str, hint: str | None = None) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    if hint:
        print(f"\n{hint}", file=sys.stderr)
    sys.exit(1)


def ensure_say() -> str:
    say_path = shutil.which("say")
    if not say_path:
        error_exit(
            "macOS 'say' command not found",
            "This script requires macOS with the built-in say command.",
        )
    return say_path


def check_config() -> None:
    ensure_say()
    print("OK: say command is available")


def list_voices() -> None:
    ensure_say()
    result = subprocess.run(
        ["say", "-v", "?"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        error_exit(result.stderr.strip() or "Unable to list voices")
    print(result.stdout, end="")


def speak(text: str, voice: str | None, rate: int | None, output: Path | None) -> Path | None:
    ensure_say()
    cmd = ["say"]
    if voice:
        cmd.extend(["-v", voice])
    if rate is not None:
        cmd.extend(["-r", str(rate)])

    output_path: Path | None = None
    if output is not None:
        output_path = output.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["-o", str(output_path)])

    cmd.append(text)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        error_exit(result.stderr.strip() or "say command failed")

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Speak text using macOS say")
    parser.add_argument("--text", "-t", help="Text to speak")
    parser.add_argument("--voice", "-v", help="Voice name (for example: Alex)")
    parser.add_argument("--rate", "-r", type=int, help="Speech rate in words per minute")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Optional output file path (.aiff)",
    )
    parser.add_argument("--list-voices", action="store_true", help="List available voices")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate local TTS configuration without speaking",
    )
    args = parser.parse_args()

    if args.check:
        check_config()
        return

    if args.list_voices:
        list_voices()
        if not args.text:
            return

    if not args.text:
        parser.error("--text is required unless using --check or --list-voices")

    output_path = speak(args.text, args.voice, args.rate, args.output)
    if output_path is not None:
        print(output_path)


if __name__ == "__main__":
    main()
