#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Test script for fetch_youtube.py

Verifies the main script works correctly with known test cases.
Run with: uv run test_fetch.py
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
FETCH_SCRIPT = SCRIPT_DIR / "fetch_youtube.py"

# Test video: Rick Astley - Never Gonna Give You Up
# Chosen because it's always available and has transcripts
TEST_VIDEO_ID = "dQw4w9WgXcQ"


def run_fetch(args: list[str]) -> tuple[dict | None, str]:
    """Run fetch_youtube.py with given args and return parsed JSON."""
    cmd = ["uv", "run", str(FETCH_SCRIPT)] + args
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0 and not result.stdout:
        return None, f"Script failed: {result.stderr}"

    try:
        return json.loads(result.stdout), ""
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON output: {e}\nOutput: {result.stdout}"


def test_basic_fetch():
    """Test basic fetch with video ID."""
    print("Testing basic fetch with video ID...")
    data, err = run_fetch([TEST_VIDEO_ID])

    if err:
        print(f"  FAIL: {err}")
        return False

    if data.get("video_id") != TEST_VIDEO_ID:
        print(f"  FAIL: Wrong video_id: {data.get('video_id')}")
        return False

    if "metadata" not in data:
        print("  FAIL: No metadata in response")
        return False

    if "transcript" not in data:
        print("  FAIL: No transcript in response")
        return False

    print("  PASS")
    return True


def test_url_formats():
    """Test various YouTube URL formats."""
    urls = [
        f"https://www.youtube.com/watch?v={TEST_VIDEO_ID}",
        f"https://youtu.be/{TEST_VIDEO_ID}",
        f"https://youtube.com/watch?v={TEST_VIDEO_ID}&t=30",
        f"https://www.youtube.com/embed/{TEST_VIDEO_ID}",
    ]

    print("Testing URL format parsing...")
    all_passed = True

    for url in urls:
        data, err = run_fetch([url])
        if err or data.get("video_id") != TEST_VIDEO_ID:
            print(f"  FAIL: {url}")
            all_passed = False
        else:
            print(f"  PASS: {url}")

    return all_passed


def test_metadata_fields():
    """Verify metadata contains expected fields."""
    print("Testing metadata fields...")
    data, err = run_fetch([TEST_VIDEO_ID, "--metadata-only"])

    if err:
        print(f"  FAIL: {err}")
        return False

    metadata = data.get("metadata", {})
    required_fields = ["title", "channel", "duration_seconds", "duration_formatted"]

    for field in required_fields:
        if field not in metadata:
            print(f"  FAIL: Missing field: {field}")
            return False

    if "Rick Astley" not in metadata.get("title", ""):
        print(f"  FAIL: Unexpected title: {metadata.get('title')}")
        return False

    print("  PASS")
    return True


def test_transcript_structure():
    """Verify transcript contains text but not segments by default."""
    print("Testing transcript structure (default, no segments)...")
    data, err = run_fetch([TEST_VIDEO_ID, "--transcript-only"])

    if err:
        print(f"  FAIL: {err}")
        return False

    transcript = data.get("transcript", {})

    if "text" not in transcript:
        print("  FAIL: Missing 'text' field")
        return False

    if "segments" in transcript:
        print("  FAIL: 'segments' should not be present by default")
        return False

    if len(transcript.get("text", "")) < 100:
        print("  FAIL: Transcript text too short")
        return False

    print("  PASS")
    return True


def test_with_segments_flag():
    """Verify --with-segments includes segments in output."""
    print("Testing --with-segments flag...")
    data, err = run_fetch([TEST_VIDEO_ID, "--transcript-only", "--with-segments"])

    if err:
        print(f"  FAIL: {err}")
        return False

    transcript = data.get("transcript", {})

    if "text" not in transcript:
        print("  FAIL: Missing 'text' field")
        return False

    if "segments" not in transcript:
        print("  FAIL: Missing 'segments' field with --with-segments")
        return False

    segments = transcript.get("segments", [])
    if len(segments) < 10:
        print(f"  FAIL: Too few segments: {len(segments)}")
        return False

    segment = segments[0]
    if "start" not in segment or "text" not in segment:
        print("  FAIL: Segment missing required fields")
        return False

    print("  PASS")
    return True


def test_invalid_url():
    """Test error handling for invalid URL."""
    print("Testing invalid URL handling...")
    data, err = run_fetch(["not-a-valid-url"])

    if err:
        print(f"  FAIL: Script error: {err}")
        return False

    if not data.get("errors"):
        print("  FAIL: Expected error in response")
        return False

    print("  PASS")
    return True


def main():
    print(f"Testing fetch_youtube.py with video: {TEST_VIDEO_ID}\n")

    tests = [
        test_basic_fetch,
        test_url_formats,
        test_metadata_fields,
        test_transcript_structure,
        test_with_segments_flag,
        test_invalid_url,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append(False)
        print()

    passed = sum(results)
    total = len(results)

    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
