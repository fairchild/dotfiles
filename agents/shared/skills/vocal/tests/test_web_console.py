#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Tests for the vocal web console helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
WEB_CONSOLE_PATH = SKILL_DIR / "scripts" / "web_console.py"


def load_web_console():
    spec = importlib.util.spec_from_file_location("vocal_web_console", WEB_CONSOLE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def test_sanitize_preferences() -> None:
    web = load_web_console()
    prefs = web.sanitize_preferences(
        {
            "ttsProvider": "elevenlabs",
            "sttProvider": "bogus",
            "sampleText": " hello ",
            "localRate": 999,
            "recordSeconds": -10,
            "useMacSpeaker": 1,
        }
    )
    assert_equal(prefs["ttsProvider"], "elevenlabs", "tts provider")
    assert_equal(prefs["sttProvider"], "local", "invalid stt provider falls back")
    assert_equal(prefs["sampleText"], "hello", "sample text trimmed")
    assert_equal(prefs["localRate"], 360, "rate clamped")
    assert_equal(prefs["recordSeconds"], 1, "duration clamped")
    assert_equal(prefs["useMacSpeaker"], True, "speaker bool")


def test_preferences_round_trip() -> None:
    web = load_web_console()
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        saved = web.save_preferences(data_dir, {"localVoice": "Samantha", "localRate": 205})
        loaded = web.load_preferences(data_dir)
        assert_equal(loaded, saved, "loaded preferences")
        payload = json.loads((data_dir / "preferences.json").read_text(encoding="utf-8"))
        assert_equal(payload["localVoice"], "Samantha", "preference file voice")


def test_voice_parsers() -> None:
    web = load_web_console()
    local = web.parse_local_voices("Alex                en_US\nBad News            en_US\n")
    cloud = web.parse_tabbed_voices("George\tvoice-id-1\nSarah\tvoice-id-2\n")
    assert_equal(local[0]["name"], "Alex", "local voice name")
    assert_equal(local[1]["id"], "Bad News", "local voice id")
    assert_equal(cloud[0]["id"], "voice-id-1", "cloud voice id")


def test_content_disposition_parser() -> None:
    web = load_web_console()
    name, filename = web.parse_content_disposition(
        'Content-Disposition: form-data; name="audio"; filename="clip.webm"\r\n'
        "Content-Type: audio/webm\r\n"
    )
    assert_equal(name, "audio", "multipart field name")
    assert_equal(filename, "clip.webm", "multipart filename")


def test_json_bytes() -> None:
    web = load_web_console()
    payload = web.json_bytes({"ok": True})
    assert_equal(payload, b'{\n  "ok": true\n}\n', "json output")


def main() -> None:
    tests = [
        test_sanitize_preferences,
        test_preferences_round_trip,
        test_voice_parsers,
        test_content_disposition_parser,
        test_json_bytes,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
