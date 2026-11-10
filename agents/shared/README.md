# Shared agent source

This directory is public source, not runtime. Installation creates a real `~/.agents/` directory outside the Git checkout and materializes the shared skill inventory there.

Skills I write are authored in [dotclaude](https://github.com/fairchild/dotclaude) and live at `~/.claude/skills`. This repo links them into `~/.agents/skills` so every agent reads the same copy; it keeps no copies of its own.

## Tracked source

- `third-party-skills.lock.json` — immutable upstream source, commit, skill path, and Git tree.
- `third-party-patches/` — narrow attributed changes applied after upstream verification.
- `prompts/` and `scripts/` — public read-only assets linked into `~/.agents/`.

The ignored `skills/` and `runtime-backups/` paths exist only so older installations cannot accidentally publish them. `mise run install:agents` moves any such legacy runtime into timestamped private backups before restoring the new topology.

## Generated runtime

```text
~/.agents/                       real generated directory
├── skills/                      real runtime directory
│   ├── <dotclaude skill>/       symlink to ~/.claude/skills/<name>
│   └── <third-party>/           verified copy plus .dotfiles-managed.json
├── prompts -> public source
└── scripts -> public source

~/.pi/agent/skills -> ~/.agents/skills
```

Claude and Codex may link selected skills from `~/.agents/skills` into their own runtime directories. Harness-local skills remain beside those links.

## Restore and inspect

```sh
mise run install:agents
mise run install:skills
~/.agents/scripts/check-shared-skills.sh
```

Every real skill directory in `~/.claude/skills` is linked, tracked or local tier; entries there that are themselves symlinks are skipped, and a name the lock claims stays third-party. Links into dotclaude or the retired `first-party-skills/` store whose source is gone are pruned. Without `~/.claude/skills` the step is skipped. Set `DOTFILES_DOTCLAUDE_SKILLS` to link from another directory.

Set `DOTFILES_SKIP_THIRD_PARTY_SKILLS=1` to link dotclaude skills only. Existing ambiguous paths are never overwritten: they move under `~/.local/share/dotfiles/migration-backups/` first.
