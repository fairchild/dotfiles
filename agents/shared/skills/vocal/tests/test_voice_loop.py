#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Non-interactive vocal loop test.

Usage:
  uv run tests/test_voice_loop.py            # Local file-based ask/listen/respond
  uv run tests/test_voice_loop.py --cloud    # Include ElevenLabs file-based loop

This test avoids microphone input by using file-based STT.
Exit codes: 0 = pass, 1 = failure.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def read_fixture(path: Path, fallback: str) -> str:
    if not path.exists():
        return fallback
    text = path.read_text(encoding="utf-8").strip()
    return text or fallback


def env_has_elevenlabs_key() -> bool:
    return bool(os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_LABS_API_KEY"))


def run(cmd: list[str], timeout: int = 120) -> tuple[bool, str, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "", f"timeout ({timeout}s)"
    except Exception as exc:
        return False, "", str(exc)

    if result.returncode != 0:
        return False, result.stdout.strip(), result.stderr.strip() or "unknown error"
    return True, result.stdout.strip(), result.stderr.strip()


def assert_audio_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing output file: {path}"
    size = path.stat().st_size
    if size <= 0:
        return False, f"empty output file: {path}"
    return True, f"audio bytes={size}"


def keyword_in_transcript(transcript: str, keyword: str) -> bool:
    return keyword.lower() in transcript.lower()


def local_loop(prompt: str, keyword: str, tmp: Path) -> tuple[bool, str]:
    tts_local = SCRIPTS_DIR / "tts_local.py"
    stt_local = SCRIPTS_DIR / "stt_local.py"

    user_audio = tmp / "user_local.aiff"
    assistant_audio = tmp / "assistant_local.aiff"

    ok, _, err = run(["uv", "run", str(tts_local), "--text", prompt, "--output", str(user_audio)])
    if not ok:
        return False, f"local ask TTS failed: {err}"

    ok, msg = assert_audio_file(user_audio)
    if not ok:
        return False, msg

    ok, stdout, err = run(["uv", "run", str(stt_local), "--file", str(user_audio)], timeout=300)
    if not ok:
        return False, f"local listen STT failed: {err}"

    transcript = stdout.strip()
    if not transcript:
        return False, "local transcript empty"
    if not keyword_in_transcript(transcript, keyword):
        return False, f"local transcript missing keyword '{keyword}': {transcript}"

    response = f"Acknowledged: {transcript}"
    ok, _, err = run(["uv", "run", str(tts_local), "--text", response, "--output", str(assistant_audio)])
    if not ok:
        return False, f"local response TTS failed: {err}"

    ok, msg = assert_audio_file(assistant_audio)
    if not ok:
        return False, msg

    return True, f"local transcript='{transcript}' ({msg})"


def cloud_loop(prompt: str, keyword: str, tmp: Path) -> tuple[bool, str]:
    if not env_has_elevenlabs_key():
        return False, "ELEVENLABS_API_KEY or ELEVEN_LABS_API_KEY is required for --cloud"

    tts_elevenlabs = SCRIPTS_DIR / "tts_elevenlabs.py"
    stt_elevenlabs = SCRIPTS_DIR / "stt_elevenlabs.py"

    user_audio = tmp / "user_cloud.mp3"
    assistant_audio = tmp / "assistant_cloud.mp3"

    ok, _, err = run(["uv", "run", str(tts_elevenlabs), "--text", prompt, "--output", str(user_audio)], timeout=300)
    if not ok:
        return False, f"cloud ask TTS failed: {err}"

    ok, msg = assert_audio_file(user_audio)
    if not ok:
        return False, msg

    ok, stdout, err = run(["uv", "run", str(stt_elevenlabs), "--file", str(user_audio)], timeout=300)
    if not ok:
        return False, f"cloud listen STT failed: {err}"

    transcript = stdout.strip()
    if not transcript:
        return False, "cloud transcript empty"
    if not keyword_in_transcript(transcript, keyword):
        return False, f"cloud transcript missing keyword '{keyword}': {transcript}"

    response = f"Acknowledged: {transcript}"
    ok, _, err = run(["uv", "run", str(tts_elevenlabs), "--text", response, "--output", str(assistant_audio)], timeout=300)
    if not ok:
        return False, f"cloud response TTS failed: {err}"

    ok, msg = assert_audio_file(assistant_audio)
    if not ok:
        return False, msg

    return True, f"cloud transcript='{transcript}' ({msg})"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run file-based voice loop tests")
    parser.add_argument("--cloud", action="store_true", help="Include ElevenLabs file-based loop")
    parser.add_argument("--prompt", help="Override prompt text")
    parser.add_argument("--keyword", help="Override required transcript keyword")
    args = parser.parse_args()

    prompt = args.prompt or read_fixture(FIXTURES_DIR / "loop_prompt.txt", "howdy from voice loop")
    keyword = args.keyword or read_fixture(FIXTURES_DIR / "expected_keyword.txt", "howdy")

    failures = 0
    print("=== Vocal Loop (File-Based) ===")
    print(f"prompt: {prompt}")
    print(f"keyword: {keyword}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        ok, msg = local_loop(prompt, keyword, tmp)
        print(f"  local: {'PASS' if ok else 'FAIL'} {msg}")
        if not ok:
            failures += 1

        if args.cloud:
            ok, msg = cloud_loop(prompt, keyword, tmp)
            print(f"  cloud: {'PASS' if ok else 'FAIL'} {msg}")
            if not ok:
                failures += 1

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
