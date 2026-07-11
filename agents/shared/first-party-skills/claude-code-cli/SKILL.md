---
name: claude-code-cli
description: Use when an agent needs to invoke the local Claude Code CLI from Codex, pi, or another shell agent; choose safe non-interactive flags; compare lean subprocess mode with full Claude Code sessions; or troubleshoot Codex-to-Claude handoffs.
license: Apache-2.0
---

# Claude Code CLI

Use `claude -p` when an agent needs Claude Code as a subprocess with captureable output.

Default stance: treat this as a controlled subprocess, not a full Claude Code session. Keep tools, MCP servers, slash commands, user settings, persistence, and budget explicit.

## Recommended Profiles

### Lean Text-Only

Use for a second opinion, wording, classification, or synthesis that does not need file access.

```sh
claude -p \
  --setting-sources project \
  --no-session-persistence \
  --disable-slash-commands \
  --strict-mcp-config \
  --mcp-config '{"mcpServers":{}}' \
  --tools "" \
  --system-prompt "You are a terse subprocess for Codex. Return only the requested final answer." \
  --output-format json \
  --max-budget-usd 0.01 \
  --model haiku \
  "$PROMPT"
```

### Read-Only Local Inspection

Use when Claude should inspect specific files. Grant only `Read` unless the user explicitly wants broader tool access.

```sh
claude -p \
  --setting-sources project \
  --no-session-persistence \
  --disable-slash-commands \
  --strict-mcp-config \
  --mcp-config '{"mcpServers":{}}' \
  --tools Read \
  --allowedTools Read \
  --system-prompt "You are a terse subprocess for Codex. Use only requested tools. Return only the requested final answer." \
  --output-format json \
  --max-budget-usd 0.02 \
  --model haiku \
  "$PROMPT"
```

### Full-Fidelity Claude Code

Use only when the task intentionally needs the user's normal Claude Code environment: skills, hooks, plugins, project/user settings, or MCP connectors.

```sh
claude -p --output-format json "$PROMPT"
```

Call this out as higher side-effect. Normal user settings may load plugins, connector MCP tools, hooks, memory, and WorkSpaces integration. Inspect resulting `~/.claude` drift if the run changes config state.

## Lessons From Local Probes

- `claude --version` was `2.1.158 (Claude Code)` when this skill was created.
- `--bare` did not work with the user's current OAuth/keychain auth path; it returned `Not logged in`.
- `--setting-sources project` kept auth working while avoiding user plugins and reducing side effects.
- `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` prevented remote connector MCP servers from loading.
- `--disable-slash-commands` means Claude skills do not load in the subprocess. This is expected for lean mode.
- `--no-session-persistence` avoided saved session files in the tested subprocess runs.
- A normal user-settings run created a `~/.claude/settings.json.workspaces-backup-*` file during testing; prefer project-scoped settings for subprocess calls unless full fidelity is required.

## Operating Rules

- Prefer `haiku` for quick subprocess probes; choose stronger models only when the work justifies the cost.
- Prefer `--output-format json` so the caller can parse `result`, cost, errors, session id, and permission denials.
- Keep `--max-budget-usd` set. If a valid answer returns with an over-budget exit code, raise the budget slightly and rerun.
- Never grant `Bash`, `Edit`, or write tools by default. Make write-capable Claude subprocesses a deliberate user-approved mode.
- If Claude is being used as a reviewer, pass it bounded context and ask for findings, risks, or alternatives. Codex remains responsible for acting on the result.
