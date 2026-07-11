# Shared agent source

This directory is public source, not runtime. Installation creates a real `~/.agents/` directory outside the Git checkout and materializes the shared skill inventory there.

## Tracked source

- `first-party-skills/` — authored and maintained here; runtime entries link back to these read-only directories.
- `third-party-skills.lock.json` — immutable upstream source, commit, skill path, and Git tree.
- `third-party-patches/` — narrow attributed changes applied after upstream verification.
- `prompts/` and `scripts/` — public read-only assets linked into `~/.agents/`.

The ignored `skills/` and `runtime-backups/` paths exist only so older installations cannot accidentally publish them. `mise run install:agents` moves any such legacy runtime into timestamped private backups before restoring the new topology.

## Generated runtime

```text
~/.agents/                       real generated directory
├── skills/                      real runtime directory
│   ├── <first-party>/           symlink to public first-party source
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

Set `DOTFILES_SKIP_THIRD_PARTY_SKILLS=1` for a first-party-only bootstrap. Existing ambiguous paths are never overwritten: they move under `~/.local/share/dotfiles/migration-backups/` first.
