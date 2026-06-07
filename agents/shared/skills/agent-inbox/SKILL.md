---
name: agent-inbox
license: Apache-2.0
description: File-based messaging between agents across any harness. Invoke this skill when you see "📬 unread in .agents/inbox", need to send or read agent messages, or set up an inbox. Triggers on "📬", ".agents/inbox", "agent inbox", "send message to agent", "check inbox", "agent message".
---

# Agent Inbox Protocol

File-based messaging for agents across harnesses (Claude Code, Codex, Cursor, Gemini CLI, Warp, etc.). Just filesystem operations — `mkdir`, `cat`, `mv`.

## Setup

Pick a goal-oriented slug for yourself (see **Self-naming**), resolve the shared inbox root, then create your inbox:

```bash
if common_dir=$(git rev-parse --git-common-dir 2>/dev/null); then
  case "$common_dir" in
    /*) ;;
    *) common_dir="$(git rev-parse --show-toplevel)/$common_dir" ;;
  esac
  inbox_root="$(dirname "$common_dir")/.agents/inbox"
else
  inbox_root="$PWD/.agents/inbox"
fi

mkdir -p "$inbox_root/<your-slug>"/{new,tmp,archive}
```

Inside a git repo, this stores mail beside the repo's common git directory so every worktree in the clone sees the same inbox. Outside git, it falls back to the current directory's `.agents/inbox/`.

## Send a message

Write to `tmp/`, then `mv` to `new/` (atomic — prevents partial reads). If the directory doesn't exist yet, create it with `mkdir -p` first.

```bash
mkdir -p "$inbox_root/recipient"/{new,tmp,archive}
cat > "$inbox_root/recipient/tmp/20260315T101500-auth-ready.md" << 'EOF'
---
from: my-agent
to: recipient
reply_to: ../my-agent/tmp/
timestamp: 2026-03-15T10:15:00Z
thread: auth-v2
---

Auth middleware rewrite is ready on `feat/auth-v2`.
EOF
mv "$inbox_root/recipient/tmp/20260315T101500-auth-ready.md" "$inbox_root/recipient/new/"
```

## Check for messages

```bash
ls "$inbox_root/my-agent/new/"
```

## Read and archive

```bash
cat "$inbox_root/my-agent/new/20260315T101500-auth-ready.md"
mv "$inbox_root/my-agent/new/20260315T101500-auth-ready.md" "$inbox_root/my-agent/archive/"
```

## Reply

Read `reply_to` from the message frontmatter — it points to the sender's `tmp/` directory. Write there, then `mv` to `new/`.

## Migrating old per-worktree inboxes

Old `.agents/inbox/` trees use the same message format. Resolve the new `inbox_root`, then move each agent directory into it:

```bash
old_root=/path/to/worktree/.agents/inbox
mkdir -p "$inbox_root"
mv "$old_root"/* "$inbox_root"/
```

Leave the old `.agents/` directory in place if that worktree still needs the non-git fallback; otherwise it can be removed after verifying the shared inbox has the expected agent directories.

## Self-naming

When you first need an inbox and don't already have one, name yourself:

1. Reflect on the conversation so far — what is the goal?
2. Pick a short slug (1–3 words, kebab-case) that captures that goal: `auth-rewrite`, `sidebar-focus`, `lume-validation`
3. Resolve `inbox_root` as shown in Setup
4. Create your inbox: `mkdir -p "$inbox_root/<your-slug>"/{new,tmp,archive}`
5. Use that slug as your `from` in all messages

Good names are **goal-oriented**, not role-oriented. Prefer `fix-split-focus` over `agent-1` or `debugger`. If the conversation pivots significantly, keep your original name — identity stability matters more than perfect accuracy.

## Discovery

Tell each agent the other's inbox path, or let agents discover peers by listing `$inbox_root/`. Every message carries `reply_to` so the recipient can reply without prior setup.

## Message format

Markdown with YAML frontmatter. Filename: `<YYYYMMDDTHHMMSS>-<slug>.md`

| Field | Required | Description |
|-------|----------|-------------|
| `from` | yes | Sender's agent name |
| `to` | yes | Recipient's agent name |
| `reply_to` | yes | Sender's `tmp/` dir, relative to recipient's inbox (e.g. `../sender/tmp/`) |
| `timestamp` | yes | ISO 8601 |
| `thread` | no | Topic grouping (e.g. `auth-v2`) |

## Conventions

- **Slugs are short subjects**: `auth-update`, `review-needed`, `api-ready`
- **Always write via `tmp/` then `mv` to `new/`**: atomic writes prevent partial reads
- **Archive after reading**: move from `new/` to `archive/`
- **Gitignore contents**: messages are ephemeral coordination, not project state

## Hooks & Notifications

### Stop hook — check for new mail

`scripts/check-inbox-hook.sh` scans the repo-shared inbox root (`$inbox_root/*/new/`). Silent when empty — no configuration needed.

### SessionStart hook — inbox summary

`scripts/inbox-startup.sh` prints a summary of unread messages when a session starts. Agent name comes from `$CLAUDE_SESSION_NAME` (falls back to `orchestrator`). Silent when empty, fast (<200ms).

Configure in `settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "bash ~/.claude/skills/agent-inbox/scripts/inbox-startup.sh"
      }
    ]
  }
}
```

### Wake-on-reply — notify parent via cmux

`scripts/wake-parent.sh` bridges async inbox messages to session lifecycle. After writing a reply to a parent's inbox, call it to wake the parent:

```bash
wake-parent.sh --surface <cmux-surface-ref> [--inbox-path <path>] [--agent <name>]
```

Behavior based on surface state:
- **Active claude session**: no-op (mail is already in the inbox — the stop hook picks it up on next turn)
- **Idle shell prompt**: spawns a headless `claude -p` session that reads the inbox
- **Surface gone**: warns and exits

> **Note:** The spawned headless session uses `--dangerously-skip-permissions` because there is no human at the terminal to approve tool calls. This is the pragmatic approach for now — a future permissions profile or allowlist flag would be preferable.

Requires cmux. See `cmux-orchestrator` skill for the full Wake-on-Reply pattern.
