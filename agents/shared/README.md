# ~/.agents canonical assets

This directory is the canonical runtime home for cross-agent reusable assets.
The public repository tracks first-party skill sources and a pinned third-party
lock, then materializes the runtime `skills/` directory during installation.

## Layout

- `first-party-skills/` — tracked skills authored and maintained here
- `third-party-skills.lock.json` — immutable upstream commits, paths, and Git trees
- `skills/` — ignored runtime assembled from both sources
- `prompts/` — shared prompt templates
- `scripts/` — topology helpers for linking and auditing shared assets

## Recommended topology

Use `~/.agents` as the source of truth, then mount or symlink into each runtime:

- `~/.pi/agent/skills` → whole-directory symlink to `~/.agents/skills`
- `~/.claude/skills/<name>` → per-skill symlink to `~/.agents/skills/<name>`
- `~/.codex/skills/<name>` → per-skill symlink to `~/.agents/skills/<name>`

This keeps one canonical copy of each shared skill while still allowing harness-specific local-only skills to live beside them.

## Restore the runtime

```bash
mise run install:skills
```

First-party skills are linked from `first-party-skills/`. Third-party skills are
fetched at the exact commit recorded in `third-party-skills.lock.json`, verified
against the recorded Git tree, and copied into the ignored runtime directory.
Use `DOTFILES_SKIP_THIRD_PARTY_SKILLS=1 mise run install:agents` for an offline
first-party-only bootstrap.

## Scripts

### Audit shared-skill health

```bash
~/.agents/scripts/check-shared-skills.sh
```

Checks:
- canonical directory name ↔ `name:` frontmatter consistency
- whether pi points at the canonical store
- how many Claude/Codex entries are symlinked into the canonical store
- local duplicates that shadow canonical skills
- hardcoded harness path references inside canonical skills

### Link shared skills into a runtime

Dry-run by default:

```bash
~/.agents/scripts/link-shared-skills.sh claude backlog vocal
~/.agents/scripts/link-shared-skills.sh codex vocal
~/.agents/scripts/link-shared-skills.sh pi
```

Apply changes:

```bash
~/.agents/scripts/link-shared-skills.sh --apply claude backlog vocal
~/.agents/scripts/link-shared-skills.sh --apply codex vocal
```

## Naming

- `*-quick` = speed
- `*-guided` = balanced default
- `*-strict` = high-stakes rigor

## Portability guidance

Shared skills should prefer:
- harness-neutral instructions
- relative paths inside scripts where possible
- reusable logic in `scripts/` and `references/`

Keep harness-specific wrappers thin when behavior really differs.
