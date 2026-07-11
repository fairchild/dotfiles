# Live Development

Skills must be "live" at the target path to test. Claude Code loads skills from two locations:

| Path | Scope |
|------|-------|
| `~/.claude/skills/` | Global — all sessions |
| `.claude/skills/` | Project — this repo only |

## Symlink Workflow

Use symlinks to bridge your development directory and the runtime path. This lets you edit in your repo while Claude Code reads from the runtime location.

```bash
# 1. Symlink your dev copy into runtime
ln -s /path/to/your/repo/skills/my-skill ~/.claude/skills/my-skill

# 2. Develop and test — changes are live immediately
# 3. After merge, remove symlink and restore tracked version
rm ~/.claude/skills/my-skill
```

## Key Rules

- **Symlink direction**: runtime path → dev repo (runtime points to dev)
- **Never rename/backup skill dirs in runtime** — any `SKILL.md` under `skills/` becomes a catalog entry (e.g. `my-skill.backup/SKILL.md` creates a skill named `my-skill.backup`)
- **New sessions** pick up changes; running sessions may need restart
- **Roll back**: `rm <symlink> && git -C ~/.claude checkout -- skills/my-skill`
