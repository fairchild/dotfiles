# ~/.agents canonical assets

This directory is the canonical home for cross-agent reusable assets.

## Layout

- `skills/` — shared agent skills
- `prompts/` — shared prompt templates
- `references/` — shared docs/snippets
- `templates/` — reusable instruction fragments
- `scripts/` — topology helpers for linking and auditing shared assets

## Recommended topology

Use `~/.agents` as the source of truth, then mount or symlink into each runtime:

- `~/.pi/agent/skills` → whole-directory symlink to `~/.agents/skills`
- `~/.claude/skills/<name>` → per-skill symlink to `~/.agents/skills/<name>`
- `~/.Codex/skills/<name>` → per-skill symlink to `~/.agents/skills/<name>`

This keeps one canonical copy of each shared skill while still allowing harness-specific local-only skills to live beside them.

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
~/.agents/scripts/link-shared-skills.sh claude code-review voice
~/.agents/scripts/link-shared-skills.sh codex voice
~/.agents/scripts/link-shared-skills.sh pi
```

Apply changes:

```bash
~/.agents/scripts/link-shared-skills.sh --apply claude code-review voice
~/.agents/scripts/link-shared-skills.sh --apply codex voice
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
