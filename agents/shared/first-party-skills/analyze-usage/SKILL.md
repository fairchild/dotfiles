---
name: analyze-usage
description: Analyze AI coding assistant usage patterns across Claude Code, Codex, and Cursor. Use when user asks about their coding usage, tool statistics, productivity patterns, skill popularity, session history, or wants to query their AI coding logs. Triggers include "usage", "how much have I used", "most used tools", "skill popularity", "coding stats", "productivity patterns".
license: Apache-2.0
---

# AI Coding Usage

Unified usage analyzer for Claude Code, Codex, and Cursor. Loads logs into DuckDB for SQL analysis.
The skill also provisions a canonical cross-harness reference schema from
`references/canonical-agent-schema.duckdb.sql` during database bootstrap.

## Quick Start

```bash
# Run the script (loads data on first run, incremental updates after)
scripts/analyze-usage

# Show database schema and example queries
scripts/analyze-usage --schema

# Query your data
scripts/analyze-usage query "SELECT * FROM tool_summary"
```

## Commands

| Command | Description |
|---------|-------------|
| (default) | Auto-detect changes, incremental update, show summary |
| `update` | Explicit incremental update |
| `reload` | Force reload all data (with backup) |
| `query "SQL"` | Execute SQL query |
| `search "query"` | Search conversation content |
| `shell` | Interactive DuckDB shell |
| `--schema` | Database schema with example queries |
| `--help` | Full help documentation |

## Search

```bash
# ILIKE search on conversation content (default)
scripts/analyze-usage search "memory"

# BM25 full-text search (covers content + thinking)
scripts/analyze-usage search "memory" --fts

# Search reasoning traces
scripts/analyze-usage search "memory" --thinking

# Search both content and thinking
scripts/analyze-usage search "memory" --all

# Filter by role, repo, time
scripts/analyze-usage search "refactor" --user --repo sample-repo --since 7d

# Limit results
scripts/analyze-usage search "deploy" -n 20
```

## Common Queries

```sql
-- Most used tools
SELECT * FROM tool_summary;

-- Daily usage (last 2 weeks)
SELECT * FROM daily_summary ORDER BY date DESC LIMIT 14;

-- Compare harness usage
SELECT source, COUNT(*) AS interactions
FROM interactions
GROUP BY source ORDER BY interactions DESC;

-- Skill popularity
SELECT regexp_extract(context, '"skill":"([^"]+)"', 1) as skill, COUNT(*) as uses
FROM claude_tools WHERE tool_name = 'Skill'
GROUP BY skill ORDER BY uses DESC;

-- Peak coding hours
SELECT hour_of_day, SUM(interactions) as total
FROM peak_hours GROUP BY hour_of_day ORDER BY total DESC LIMIT 5;

-- Activity by repository (aggregates worktrees)
SELECT repo_name, SUM(interactions) as total, SUM(worktrees) as branches
FROM repo_activity GROUP BY repo_name ORDER BY total DESC LIMIT 10;

-- Turn durations
SELECT * FROM turn_durations ORDER BY duration_ms DESC LIMIT 10;

-- Session overview with summaries
SELECT session_id, repo_name, summary FROM session_overview
WHERE summary IS NOT NULL ORDER BY started_at DESC LIMIT 10;

-- API errors
SELECT * FROM api_errors ORDER BY timestamp DESC LIMIT 10;

-- PR links
SELECT * FROM pr_links;

-- Cost by repo
SELECT repo_name, ROUND(SUM(cost_usd), 2) as cost
FROM usage_with_cost
WHERE CAST(timestamp AS TIMESTAMP) >= CURRENT_DATE - INTERVAL 7 DAY
GROUP BY repo_name ORDER BY cost DESC;

-- Full cost summary by repo and model
SELECT * FROM cost_summary ORDER BY cost_usd DESC;
```

## Cost Calculation

The script tracks tokens and calculates API costs automatically:

**Token columns** in `claude_tools`:
- `input_tokens`, `output_tokens` - Direct tokens
- `cache_write_tokens`, `cache_read_tokens` - Prompt caching tokens
- `model` - Model used (opus/sonnet/haiku)

**Cost views**:
- `model_pricing` - API rates per million tokens (update when prices change)
- `usage_with_cost` - Each row has pre-calculated `cost_usd`
- `cost_summary` - Pre-aggregated by repo/model

## Key Tables/Views

### Core Tables
- `claude_tools` - Tool invocations (with model, tokens, repo/branch, source_file)
- `claude_sessions` - Session metadata
- `codex_tools` - Codex tool invocations
- `codex_sessions` - Codex session metadata
- `codex_token_counts` - Codex per-turn token snapshots
- `codex_developer_messages` - Codex developer-role instruction payloads
- `messages` - Conversation content (user text, assistant text + thinking)
- `system_events` - System records (turn_duration, api_error, stop_hook_summary)
- `queue_operations` - User inputs queued during assistant response
- `pr_links` - Session-to-PR mappings
- `_sessions_index` - Session metadata from sessions-index.json (summary, first_prompt)
- `_loaded_files` - File mtime tracking for incremental loading

### Canonical Reference Tables
- `agent_sessions` - Canonical sessions with `id` primary key and `external_session_id`
- `agent_raw_events` - Raw imported events keyed by `agent_session_id`
- `agent_contexts` - Context changes keyed by `agent_session_id` / `agent_raw_event_id`
- `agent_events` - Normalized events keyed by `agent_session_id`, `agent_context_id`, `agent_raw_event_id`
- `agent_parts` - Structured event parts keyed by `agent_event_id`
- `agent_tool_calls` - Tool invocations keyed by `agent_event_id`
- `agent_tool_results` - Tool outputs keyed by `agent_event_id` / `agent_tool_call_id`
- `agent_tokens` - Token and cost summaries keyed by `agent_event_id`

### Views
- `turn_durations` - Response timing from system events
- `api_errors` - API error events
- `session_overview` - Sessions joined with index metadata
- `interactions` - Unified view (Claude + Codex + Cursor)
- `conversation_search` - Messages with content/thinking previews
- `session_messages` - Per-session aggregation with topic
- `recent_conversations` - Last 50 sessions
- `conversation_pairs` - User/assistant turns joined on parent_uuid
- `message_stats` - Daily message volume by harness/role
- `repo_activity` - Repository-level summary (aggregates worktrees)
- `project_activity` - Project-level with worktree info
- `usage_with_cost` - Tool invocations with pre-calculated `cost_usd`
- `cost_summary` - Pre-aggregated costs by repo/model
- `model_pricing` - API rates (editable)

Run `--schema` for complete documentation.
When the script is installed standalone, copy the same canonical schema file to
`~/.local/share/analyze-usage/` so bootstrap still uses the checked-in DDL.

## Testing

```bash
uv run skills/analyze-usage/tests/test_analyze_usage.py
```

This regression harness covers fresh bootstrap, canonical schema discovery, and
legacy upgrade behavior for `update`.
