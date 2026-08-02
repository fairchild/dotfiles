#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Regression tests for the mise pin updater."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tomllib
import unittest


SCRIPT = Path(__file__).with_name("update-mise-pin.py")
SPEC = importlib.util.spec_from_file_location("update_mise_pin", SCRIPT)
assert SPEC and SPEC.loader
updater = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = updater
SPEC.loader.exec_module(updater)

FIXTURE = """[mise]
version = "v2026.7.5"
released_at = "2026-07-09T21:12:51Z"
release_url = "https://github.com/jdx/mise/releases/tag/v2026.7.5"
asset_url_template = "https://example.invalid/{version}/{platform}"
shasums_url = "https://example.invalid/v2026.7.5/SHASUMS256.asc"

[mise.sha256]
"linux-x64" = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
"linux-arm64" = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
"macos-x64" = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
"macos-arm64" = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"

[mise.signing]
fingerprint = "leave-this-alone"

[gitleaks]
version = "v8.30.1"
linux_x64_sha256 = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
"""

NEW_SHAS = {
    "linux-x64": "1" * 64,
    "linux-arm64": "2" * 64,
    "macos-x64": "3" * 64,
    "macos-arm64": "4" * 64,
}


class UpdateMisePinTests(unittest.TestCase):
    def test_updates_only_approved_mise_fields(self) -> None:
        rewritten = updater.rewrite_pin(
            FIXTURE,
            version="v2026.7.14",
            released_at="2026-07-26T16:26:10Z",
            shas=NEW_SHAS,
        )
        parsed = tomllib.loads(rewritten)

        self.assertEqual(parsed["mise"]["version"], "v2026.7.14")
        self.assertEqual(parsed["mise"]["sha256"], NEW_SHAS)
        self.assertEqual(parsed["mise"]["signing"]["fingerprint"], "leave-this-alone")
        self.assertEqual(parsed["gitleaks"]["version"], "v8.30.1")
        self.assertEqual(
            FIXTURE.split("[gitleaks]", 1)[1], rewritten.split("[gitleaks]", 1)[1]
        )

    def test_rejects_invalid_sha_without_producing_output(self) -> None:
        invalid = dict(NEW_SHAS)
        invalid["linux-x64"] = "not-a-sha"

        with self.assertRaisesRegex(ValueError, "invalid SHA-256"):
            updater.rewrite_pin(
                FIXTURE,
                version="v2026.7.14",
                released_at="2026-07-26T16:26:10Z",
                shas=invalid,
            )

    def test_rejects_missing_scoped_key(self) -> None:
        without_version = FIXTURE.replace('version = "v2026.7.5"\n', "", 1)

        with self.assertRaisesRegex(ValueError, "mise.version"):
            updater.rewrite_pin(
                without_version,
                version="v2026.7.14",
                released_at="2026-07-26T16:26:10Z",
                shas=NEW_SHAS,
            )


if __name__ == "__main__":
    unittest.main()
