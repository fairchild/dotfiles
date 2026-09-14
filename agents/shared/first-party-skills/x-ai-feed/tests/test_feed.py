#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Offline tests for the x-ai-feed parser and renderer."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("x_ai_feed", SKILL_DIR / "scripts" / "feed.py")
assert SPEC and SPEC.loader
feed = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = feed
SPEC.loader.exec_module(feed)


class FeedTests(unittest.TestCase):
    def test_parse_profile_accepts_iso_and_rfc_dates(self) -> None:
        markdown = """# Example Person (@example)
- Verified: yes

### 1. Post
Posted: 2026-07-31T12:00:00Z
URL: [post](https://x.com/example/status/1)

> First post
Likes: 1,234 | Retweets: 56

### 2. Post
Posted: Thu, 30 Jul 2026 12:00:00 +0000
URL: [post](https://x.com/example/status/2)

> Second post
Likes: 7 | Retweets: 8

### 3. Post
Posted: 2026-07-31T12:00:00Z
URL: [post](javascript:alert(1))

> Unsafe link
Likes: 9 | Retweets: 10
"""

        posts, author = feed.parse_profile(markdown, "example", "Builders")

        self.assertEqual(author, "Example Person")
        self.assertEqual(len(posts), 2)
        self.assertTrue(all(post.verified for post in posts))
        self.assertEqual(posts[0].likes, 1234)
        self.assertEqual(posts[1].posted, "2026-07-30T12:00:00Z")

    def test_render_escapes_script_closing_sequences(self) -> None:
        post = feed.Post(
            handle="example",
            author="Example",
            verified=False,
            category="Builders",
            posted="2026-07-31T12:00:00Z",
            url="https://x.com/example/status/1",
            text="before </script> after",
            likes=1,
            retweets=0,
        )
        meta = {"story_count": 1}

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            template = temp / "template.html"
            output = temp / "feed.html"
            template.write_text(
                "<script>const posts=__FEED_DATA_JSON__;const meta=__META_JSON__;</script>",
                encoding="utf-8",
            )

            feed.render([post], meta, template, output)
            rendered = output.read_text(encoding="utf-8")

        self.assertNotIn("before </script> after", rendered)
        self.assertIn(r"before <\/script> after", rendered)
        self.assertIn(json.dumps(meta), rendered)


if __name__ == "__main__":
    unittest.main()
