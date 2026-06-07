# agent-inbox

File-based messaging between AI coding agents, across any harness.

## When to use this

- You have agents in **different tools** (Claude Code, Codex, Cursor, Gemini CLI, Warp) that need to coordinate on the same project.
- You want agent-to-agent communication that **doesn't require a daemon, MCP server, or network**.
- You need something simpler than Claude Code's TeamCreate — just drop a file, read a file.

## How it works

Each agent gets a directory under the shared inbox root:

```
$inbox_root/agent-name/
  new/          # unread messages land here
  tmp/          # write-in-progress (atomic safety)
  archive/      # read messages get moved here
```

Inside a git repo, `inbox_root` is derived from `git rev-parse --git-common-dir` and lives beside the clone's common `.git` directory. All worktrees in that clone share the same inbox. Outside git, it falls back to `$PWD/.agents/inbox`.

Messages are markdown files with YAML frontmatter. Filenames are timestamped with a topic slug: `20260315T101500-auth-ready.md`.

Discovery is human-brokered: you tell each agent where the other's inbox is. Every message carries a `reply_to` path so the recipient can reply without prior setup.

## Example

```bash
# Resolve inbox root
if common_dir=$(git rev-parse --git-common-dir 2>/dev/null); then
  case "$common_dir" in
    /*) ;;
    *) common_dir="$(git rev-parse --show-toplevel)/$common_dir" ;;
  esac
  inbox_root="$(dirname "$common_dir")/.agents/inbox"
else
  inbox_root="$PWD/.agents/inbox"
fi

# Create inboxes
mkdir -p "$inbox_root/alice"/{new,tmp,archive}
mkdir -p "$inbox_root/bob"/{new,tmp,archive}

# Alice sends to Bob
cat > "$inbox_root/bob/tmp/20260315T101500-api-ready.md" << 'EOF'
---
from: alice
to: bob
reply_to: ../alice/tmp/
timestamp: 2026-03-15T10:15:00Z
---

Endpoints are live on `feat/api`.
EOF
mv "$inbox_root/bob/tmp/20260315T101500-api-ready.md" "$inbox_root/bob/new/"

# Bob checks and reads
ls "$inbox_root/bob/new/"
cat "$inbox_root/bob/new/20260315T101500-api-ready.md"
mv "$inbox_root/bob/new/20260315T101500-api-ready.md" "$inbox_root/bob/archive/"

# Bob replies using reply_to path from the message
cat > "$inbox_root/alice/tmp/20260315T102000-ack.md" << 'EOF'
---
from: bob
to: alice
reply_to: ../bob/tmp/
timestamp: 2026-03-15T10:20:00Z
---

Got it, pulling now.
EOF
mv "$inbox_root/alice/tmp/20260315T102000-ack.md" "$inbox_root/alice/new/"
```

## Migrating existing inboxes

Old per-worktree `.agents/inbox/` directories use the same layout and message files. Resolve `inbox_root`, move the old agent directories into it, then verify every agent sees the same `$inbox_root` from each worktree:

```bash
old_root=/path/to/worktree/.agents/inbox
mkdir -p "$inbox_root"
mv "$old_root"/* "$inbox_root"/
```

## "You've got mail" hook

An optional Stop hook scans the shared inbox root and nudges the agent with a one-line `📬` notification. Silent when empty — no configuration needed.

```json
{
  "Stop": [{
    "hooks": [{
      "type": "command",
      "command": "~/.claude/skills/agent-inbox/scripts/check-inbox-hook.sh"
    }]
  }]
}
```

## Design choices

- **Markdown over JSON** — agents already speak markdown. Messages are human-readable with `cat`.
- **Atomic writes** — write to `tmp/`, rename to `new/`. No partial reads.
- **Gitignored** — messages are ephemeral coordination, not project state.
- **No scripts required** — the protocol is `mkdir`, `cat`, and `mv`.
- **No registry** — discovery comes from the repo-shared inbox root, still brokered by the human when needed.
- **Cross-harness by design** — the filesystem is the only dependency.
