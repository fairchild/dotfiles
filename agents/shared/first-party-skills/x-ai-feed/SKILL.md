---
name: x-ai-feed
description: Build a self-contained local HTML feed of recent posts from curated high-signal X accounts, for staying current on AI news/papers/projects without doom-scrolling. Use when asked to refresh the AI feed, check what's new on X, or update the news dispatch.
---

# X AI Feed

Builds `~/x-ai-feed/feed.html`: a standalone page listing recent posts from a
curated list of X handles, grouped by category, newest first. No X API
account or MCP server required — it scrapes public profile pages via the
`firecrawl` CLI (check authentication with
`firecrawl --status`).

This trades the official X API's reliability for zero recurring cost: no
X Developer Portal signup, no $200+/mo API tier. The tradeoff is that it
depends on Firecrawl successfully rendering `x.com` profile pages, which can
change or get rate-limited without notice — if a run comes back mostly
empty or `firecrawl --status` shows depleted credits, that's the first thing
to check.

## Running it

```bash
~/.agents/skills/x-ai-feed/scripts/feed.py
```

Flags (all optional):
- `--lookback-hours N` (default 24) — only include posts newer than this
- `--max-stories N` (default 60) — cap on total stories in the feed
- `--sources PATH` (default `sources.json` next to this skill)
- `--output PATH` (default `~/x-ai-feed/feed.html`)

Each run costs one Firecrawl credit per handle in `sources.json` — check
`firecrawl --status` before widening the source list or tightening the
schedule.

## Workflow

1. Confirm `sources.json` exists and has handles the user actually wants
   tracked. If the user asks to add/remove/recategorize accounts, edit
   `sources.json` directly (it's a small hand-editable list, not generated).
2. Run `scripts/feed.py` with whatever `--lookback-hours` fits the ask (a
   daily catch-up vs. "what happened since yesterday").
3. Report back: story count, source count, and which handles (if any) came
   back empty (`errors` in the printed output / `meta.errors` in the page) —
   don't just say "done," name what's missing so the user can judge if a
   rerun or a `sources.json` edit is warranted.
4. Open `~/x-ai-feed/feed.html` (or point the user to it) rather than
   summarizing its contents in chat — the whole point is a page they browse
   themselves.

## Editing sources

`sources.json` has a flat `categories` list and a `sources` list of
`{handle, category}` pairs (handle without `@`). Categories in `sources.json`
drive both the on-page filter tabs and the badge on each entry — keep the
category set small (4-6) or the tab row gets unwieldy.

## Scheduling

For recurring runs (e.g. every 4 hours), use the current harness's automation
or scheduling facility to run the command above on an interval. Set this up
only if the user asks for it, since it is a standing automation, not a one-off.

## Design notes for template.html

`assets/template.html` is a static template with two replacement tokens,
`__FEED_DATA_JSON__` and `__META_JSON__`, filled in by `feed.py` via plain
string substitution (no templating engine). If the visual design needs
changing, edit the template directly — the data contract (`Post` fields in
`feed.py`: handle, author, verified, category, posted, url, text, likes,
retweets) is the thing not to break.
