# analyze-usage

Unified usage analyzer for AI coding assistants (Claude Code, Codex, and Cursor).

Loads local logs into a **persistent DuckDB database** for SQL-based analysis. Designed to be agent-friendly with comprehensive `--help` and `--schema` documentation.

## Quick Start

```bash
# Install
install -Dm755 skills/analyze-usage/scripts/analyze-usage ~/.local/bin/analyze-usage
install -Dm644 skills/analyze-usage/references/canonical-agent-schema.duckdb.sql \
  ~/.local/share/analyze-usage/canonical-agent-schema.duckdb.sql

# First run - loads data and shows summary
analyze-usage

# See what's available
analyze-usage --schema

# Query your data
analyze-usage query "SELECT * FROM tool_summary"
```

## Features

- **Unified**: Loads Claude Code, Codex, and Cursor data into one database
- **Incremental**: Auto-detects new/changed files and updates only what's needed
- **Persistent**: DuckDB database persists between runs (`~/.local/share/analyze-usage/usage.duckdb`)
- **Safe**: Timestamped backup before every load/reload
- **Agent-friendly**: `--help` and `--schema` provide complete documentation for AI agents
- **Canonical schema**: Installs and bootstraps the cross-harness reference schema
- **Fast**: DuckDB is extremely fast for analytical queries

## Commands

| Command | Description |
|---------|-------------|
| `analyze-usage` | Auto-detect changes, incremental update, show summary |
| `analyze-usage update` | Explicit incremental update |
| `analyze-usage reload` | Force reload all data (with backup) |
| `analyze-usage --help` | Detailed help documentation |
| `analyze-usage --schema` | Database schema with example queries |
| `analyze-usage query "SQL"` | Execute a SQL query |
| `analyze-usage search "query"` | Search conversation content |
| `analyze-usage shell` | Open interactive DuckDB shell |

## For AI Agents

This tool is designed to be used by AI coding agents. To analyze usage:

1. Run `analyze-usage --schema` to get the complete database schema
2. Write SQL queries based on the schema documentation
3. Execute queries with `analyze-usage query "YOUR SQL"`

## Search

Search conversation content across all indexed sessions:

```bash
# ILIKE search (default)
analyze-usage search "memory"

# BM25 full-text search
analyze-usage search "memory" --fts

# Search reasoning traces
analyze-usage search "memory" --thinking

# Search both content and thinking
analyze-usage search "memory" --all

# Filters
analyze-usage search "refactor" --user --repo bertram-chat --since 7d -n 20
```

| Flag | Description |
|------|-------------|
| `--thinking` | Search reasoning traces instead of content |
| `--all` | Search both content and thinking |
| `--fts` | BM25 ranked full-text search |
| `-n N` | Limit results (default 10) |
| `--user` | User messages only |
| `--asst` | Assistant messages only |
| `--repo X` | Filter to repository |
| `--since T` | Time filter (7d, 4w, or YYYY-MM-DD) |

## Database Schema (Summary)

### Core Tables

| Table | Description |
|-------|-------------|
| `claude_tools` | Claude Code tool invocations (with source_file for incremental) |
| `claude_sessions` | Claude Code session metadata |
| `messages` | Conversation content (user text, assistant text + thinking) |
| `codex_tools` | Codex tool invocations |
| `codex_sessions` | Codex session metadata |
| `codex_token_counts` | Codex per-turn token snapshots |
| `codex_developer_messages` | Codex developer-role instruction payloads |
| `cursor_prompts` | Cursor user prompts |
| `cursor_workspaces` | Cursor workspace metadata |
| `system_events` | System records: turn_duration, api_error, stop_hook_summary |
| `queue_operations` | User inputs queued during assistant responses |
| `pr_links` | Session-to-PR mappings |
| `_sessions_index` | Session metadata from sessions-index.json (summary, first_prompt) |
| `_loaded_files` | File mtime tracking for incremental loading |

### Views

| View | Description |
|------|-------------|
| `turn_durations` | Response timing from system events |
| `api_errors` | API error events |
| `session_overview` | Sessions joined with index metadata (summary, first_prompt) |

### Unified Views (Cross-Tool Analysis)

| View | Description |
|------|-------------|
| `interactions` | **Primary unified view** - all interactions normalized to one schema |
| `daily_by_source` | Daily counts separated by tool |
| `weekly_summary` | Weekly aggregation by source |
| `project_activity` | Project-level summary across both tools |
| `repo_activity` | Repository-level (aggregates worktrees) |
| `category_breakdown` | Usage by category (tool names / prompts) |
| `session_summary` | Unified session metrics |
| `peak_hours` | Find your most productive hours |
| `hourly_activity` | Time-series at hourly granularity |
| `recent_interactions` | Last 100 interactions for quick review |

### Conversation Views

| View | Description |
|------|-------------|
| `conversation_search` | Messages with content/thinking previews |
| `session_messages` | Per-session aggregation with topic extraction |
| `recent_conversations` | Last 50 sessions |
| `conversation_pairs` | User/assistant turns joined on parent_uuid |
| `message_stats` | Daily message volume by harness/role |

### Cost Views

| View | Description |
|------|-------------|
| `model_pricing` | API rates per million tokens (editable) |
| `usage_with_cost` | Tool invocations with pre-calculated `cost_usd` |
| `cost_summary` | Pre-aggregated costs by repo/model |

Run `analyze-usage --schema` for complete documentation.

## Canonical Schema Reference

The skill now ships a normalized cross-harness reference schema at
`references/canonical-agent-schema.duckdb.sql`.

- every table has an `id` primary key
- foreign keys use `{table}_id`
- provider-native identifiers use `external_*`
- every table includes `created_at` and `updated_at`

The analyzer loads this SQL file idempotently during database bootstrap, so new
and upgraded databases have the canonical tables available before the harness-
specific tables and views are populated.
When the script is installed standalone into `~/.local/bin`, it reads the same
checked-in schema file from `~/.local/share/analyze-usage/`.

## Example Queries

```sql
-- Most used tools
SELECT tool_name, COUNT(*) as uses
FROM claude_tools
GROUP BY tool_name
ORDER BY uses DESC;

-- Daily usage trend
SELECT * FROM daily_summary
ORDER BY date DESC
LIMIT 14;

-- Turn durations
SELECT * FROM turn_durations ORDER BY duration_ms DESC LIMIT 10;

-- Session overview with summaries
SELECT session_id, repo_name, summary FROM session_overview
WHERE summary IS NOT NULL ORDER BY started_at DESC LIMIT 10;

-- API errors
SELECT * FROM api_errors ORDER BY timestamp DESC;

-- PR links
SELECT * FROM pr_links;

-- Skill usage
SELECT context as skill_name, COUNT(*) as uses
FROM claude_tools
WHERE tool_name = 'Skill'
GROUP BY context
ORDER BY uses DESC;

-- Compare harness usage
SELECT
    source,
    COUNT(*) as interactions
FROM interactions
GROUP BY source
ORDER BY interactions DESC;
```

## Data Sources

### Claude Code
- **Location**: `~/.claude/projects/*/*.jsonl`
- **Contents**: Full tool invocation logs, messages, system events, queue operations, PR links
- **Metadata**: `sessions-index.json` files with session summaries

### Codex
- **Location**: `~/.codex/sessions/**/*.jsonl`, `~/.codex/archived_sessions/*.jsonl`
- **Metadata**: `~/.codex/session_index.jsonl`
- **Contents**: session metadata, user/assistant messages, tool calls, token-count snapshots, developer-role instruction payloads
- **Note**: developer-role payloads are stored separately in `codex_developer_messages` so they remain queryable without polluting default conversation search

### Cursor
- **Location**: `~/Library/Application Support/Cursor/User/workspaceStorage/*/state.vscdb`
- **Contents**: User prompts and chat history
- **Note**: Cursor does not log tool-level detail like Claude Code

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANALYZE_USAGE_DB` | `~/.local/share/analyze-usage/usage.duckdb` | Database path |
| `CLAUDE_PROJECTS_DIR` | `~/.claude/projects` | Claude Code logs path |
| `CODEX_HOME` | `~/.codex` | Codex logs path |

## Requirements

- **DuckDB** (required): `brew install duckdb` or download from [duckdb.org](https://duckdb.org)
- **jq** (optional, for Cursor workspace.json parsing)

## How It Works

1. On first run, scans source directories and loads all log files
2. On subsequent runs, auto-detects new/changed files via mtime comparison
3. Incrementally updates changed Claude files by `source_file`; Cursor and Codex are reloaded wholesale when their tracked files change
4. Creates timestamped backup before every load/reload
5. Database persists at `~/.local/share/analyze-usage/usage.duckdb`

Use `reload` to force a full rebuild from scratch.

## Testing

Run the regression test harness with:

```bash
uv run skills/analyze-usage/tests/test_analyze_usage.py
```

The test covers fresh bootstrap, canonical schema discovery, and legacy upgrade
behavior for the `update` path.
