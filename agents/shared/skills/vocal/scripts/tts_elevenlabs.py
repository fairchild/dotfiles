#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["elevenlabs", "httpx"]
# ///
"""Generate speech with ElevenLabs TTS."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import httpx
from env_helpers import get_elevenlabs_api_key

API_BASE = "https://api.elevenlabs.io/v1"


def error_exit(msg: str, hint: str | None = None) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    if hint:
        print(f"\n{hint}", file=sys.stderr)
    sys.exit(1)


def get_api_key() -> str:
    api_key = get_elevenlabs_api_key()
    if not api_key:
        error_exit(
            "ELEVENLABS_API_KEY (or ELEVEN_LABS_API_KEY) environment variable not set",
            "To fix, either:\n"
            "  1. Add to ~/.env:      ELEVENLABS_API_KEY=your-key-here\n"
            "  2. Or export in shell: export ELEVENLABS_API_KEY=your-key-here\n"
            "  3. Or legacy alias:    export ELEVEN_LABS_API_KEY=your-key-here\n\n"
            "Get your API key at: https://elevenlabs.io/app/settings/api-keys",
        )
    return api_key


def elevenlabs_headers(api_key: str) -> dict[str, str]:
    return {
        "xi-api-key": api_key,
        "accept": "application/json",
    }


def check_config() -> None:
    api_key = get_api_key()
    with httpx.Client(timeout=20) as client:
        response = client.get(f"{API_BASE}/user", headers=elevenlabs_headers(api_key))

    if response.status_code == 200:
        print("OK: ELEVENLABS_API_KEY is valid")
        return
    if response.status_code in {401, 403}:
        error_exit(
            "ELEVENLABS_API_KEY is invalid or unauthorized",
            "Get a valid key at: https://elevenlabs.io/app/settings/api-keys",
        )

    error_exit(f"ElevenLabs API check failed ({response.status_code}): {response.text}")


def fetch_voices(api_key: str) -> list[dict[str, str]]:
    with httpx.Client(timeout=20) as client:
        response = client.get(f"{API_BASE}/voices", headers=elevenlabs_headers(api_key))

    if response.status_code in {401, 403}:
        error_exit("ELEVENLABS_API_KEY is invalid or unauthorized")
    if response.status_code != 200:
        error_exit(f"Unable to fetch ElevenLabs voices ({response.status_code}): {response.text}")

    payload = response.json()
    voices = payload.get("voices", [])
    result: list[dict[str, str]] = []
    for voice in voices:
        voice_id = str(voice.get("voice_id", "")).strip()
        name = str(voice.get("name", "")).strip()
        if voice_id and name:
            result.append({"voice_id": voice_id, "name": name})
    return result


def resolve_voice_id(api_key: str, voice: str) -> str:
    raw = voice.strip()
    if not raw:
        error_exit("Voice cannot be empty")

    # ElevenLabs supports both UUID-like and compact alphanumeric voice IDs.
    if re.fullmatch(r"[A-Za-z0-9]{20,}", raw) or re.fullmatch(r"[0-9a-fA-F-]{32,36}", raw):
        return raw

    voices = fetch_voices(api_key)
    lowered = raw.lower()
    for item in voices:
        if item["name"].lower() == lowered:
            return item["voice_id"]

    starts_with_matches = [item for item in voices if item["name"].lower().startswith(lowered)]
    if len(starts_with_matches) == 1:
        return starts_with_matches[0]["voice_id"]

    contains_matches = [item for item in voices if lowered in item["name"].lower()]
    if len(contains_matches) == 1:
        return contains_matches[0]["voice_id"]

    available = ", ".join(sorted(v["name"] for v in voices[:15]))
    error_exit(
        f"Unknown voice name: {raw}",
        f"Use a voice ID, or choose a valid name. Example voices: {available}",
    )
    raise AssertionError("unreachable")


def list_voices(api_key: str) -> None:
    voices = fetch_voices(api_key)
    for item in voices:
        print(f"{item['name']}\t{item['voice_id']}")


def synthesize(text: str, voice_id: str, model: str, output_path: Path, api_key: str) -> None:
    headers = {
        "xi-api-key": api_key,
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": model,
    }

    url = f"{API_BASE}/text-to-speech/{voice_id}"
    with httpx.Client(timeout=120) as client:
        with client.stream("POST", url, headers=headers, params={"output_format": "mp3_44100_128"}, json=payload) as response:
            if response.status_code in {401, 403}:
                error_exit("ELEVENLABS_API_KEY is invalid or unauthorized")
            if response.status_code >= 400:
                body = response.read().decode("utf-8", errors="replace")
                message = body
                try:
                    parsed = json.loads(body)
                    if isinstance(parsed, dict):
                        message = str(parsed.get("detail") or parsed)
                except json.JSONDecodeError:
                    pass
                error_exit(f"ElevenLabs TTS request failed ({response.status_code}): {message}")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as f:
                for chunk in response.iter_bytes():
                    if chunk:
                        f.write(chunk)


def play_audio(path: Path) -> None:
    afplay = shutil.which("afplay")
    if not afplay:
        error_exit("'afplay' is not available on this system")

    result = subprocess.run([afplay, str(path)], capture_output=True, text=True)
    if result.returncode != 0:
        error_exit(result.stderr.strip() or "Audio playback failed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate speech with ElevenLabs")
    parser.add_argument("--text", "-t", help="Text to speak")
    parser.add_argument("--voice", "-v", default="George", help="Voice name or voice ID")
    parser.add_argument(
        "--model",
        "-m",
        default="eleven_flash_v2_5",
        help="Model ID (default: eleven_flash_v2_5)",
    )
    parser.add_argument("--output", "-o", type=Path, default=None, help="Optional output mp3 path")
    parser.add_argument("--play", action="store_true", help="Play audio after generation")
    parser.add_argument("--list-voices", action="store_true", help="List available voices")
    parser.add_argument("--check", action="store_true", help="Validate ELEVENLABS_API_KEY")
    args = parser.parse_args()

    if args.check:
        check_config()
        return

    api_key = get_api_key()

    if args.list_voices:
        list_voices(api_key)
        if not args.text:
            return

    if not args.text:
        parser.error("--text is required unless using --check or --list-voices")

    should_play = args.play or args.output is None

    cleanup_temp = False
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        temp = tempfile.NamedTemporaryFile(prefix=f"voice-tts-{timestamp}-", suffix=".mp3", delete=False)
        output_path = Path(temp.name)
        temp.close()
        cleanup_temp = True
    else:
        output_path = args.output.expanduser().resolve()

    voice_id = resolve_voice_id(api_key, args.voice)

    synthesize(args.text, voice_id, args.model, output_path, api_key)

    if should_play:
        play_audio(output_path)

    if args.output is not None:
        print(output_path)

    if cleanup_temp:
        output_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
