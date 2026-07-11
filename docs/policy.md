<!-- doc-meta { "owner": "dotfiles", "audience": "humans + agents", "freshness-window": "90d" } -->

# Policy

The constitution for `~/.config/dotfiles` and related public configuration repositories. This document describes shipped invariants and conventions; planned CLI and persona work is listed separately so readers do not mistake a roadmap for an interface.

The keel never moves. Planks come and go.

<!-- skill:start -->
---
name: dotfiles
description: House policy for Michael's public configuration source and private runtime boundaries.
type: skill
version: 0.2
---

## What this is

`~/.config/dotfiles` is the public source for shell, Git, Homebrew, and shared agent configuration. Related repositories can adopt the same mise task and source/runtime conventions without registering in a central manifest.

The shipped interface is deterministic: `mise run bootstrap`, `mise run doctor`, `mise run sync`, and the `install:*` tasks. Cross-repository aggregation is planned, not current behavior.

## Invariants

1. **`~/.claude` is always an independent git clone on `main`.** Never a worktree, never a symlink to another path, never a branch other than `main`. Worktrees go elsewhere.
2. **Whitelist `.gitignore`s.** Every public configuration repository ignores by default and opts intentional source back in.
3. **Repositories declare themselves.** A participant uses its own `.mise.toml` identity and tasks. There is no umbrella-owned registry.
4. **Pin upstream inputs.** The mise version and platform checksums live in `install/pins.toml`. Third-party skills use immutable revisions, a lockfile, and narrow local patches.
5. **Deterministic checks come first.** Hooks and required CI must not need an API key or model-backed agent.
6. **Public source and private runtime have different ownership.** Tracked source is reviewable and shareable. Secrets, identity, logs, caches, generated output, and machine-local state stay outside tracked source.

## Participation levels

- **T0:** any Git repository; generic source checks are possible.
- **T1:** `.mise.toml` exists.
- **T2:** `.mise.toml` declares `DOTFILES_NAME` and `DOTFILES_RUNTIME`.
- **T3:** deterministic `doctor` and `bootstrap` tasks are defined and runnable.

These levels are conventions for future aggregation. Repositories can adopt them today without an umbrella CLI.

## Conventions

- Mise task names: `doctor`, `bootstrap`, `sync`, `check`, `fix`, `clean`, and `install:*`.
- Public scripts carry `#MISE description="..."` as the second line. Private helpers live under `scripts/lib/` or use an underscore prefix.
- Repository identity lives in `.mise.toml`:

  ```toml
  [env]
  DOTFILES_NAME = "dotpi"
  DOTFILES_RUNTIME = "~/.pi/agent"
  ```

- Active profiles are `mac-personal`, `codespace`, and `cloud-vm`. A separate `linux-personal` contract has not shipped.
- Public base configuration includes private local overlays rather than storing identity or secrets in Git.
- Installers are conservative: back up ambiguous existing paths, avoid destructive overwrite, and make repeated runs safe.

## Blast-radius rules

- Hooks do not modify tracked dotfiles or dotclaude source.
- The public installer clones when absent and does not update an existing checkout; `mise run sync` owns updates.
- Doctor is read-only. A future fix mode must be explicit and interactive by default.
- Unknown runtime data is preserved until it is classified.
- Secret checks verify names, structure, and permissions without printing values.

## Anti-conventions

- Do not add a central participant manifest.
- Do not invoke model-backed agents from required hooks, bootstrap, doctor, or CI.
- Do not put private or generated state in tracked public paths.
- Do not copy third-party runtime trees into Git when immutable provenance can reproduce them.
- Do not describe planned commands or workflows as shipped.
- Do not delete ambiguous legacy data during migration; preserve it in a timestamped backup.

<!-- skill:end -->

## Planned surfaces

- [#2](https://github.com/fairchild/dotfiles/issues/2) tracks a minimal future cross-repository doctor/status CLI.
- [#8](https://github.com/fairchild/dotfiles/issues/8) preserves the optional Dr. Dotty persona idea without making it a release commitment.
- [#20](https://github.com/fairchild/dotfiles/issues/20) defines the stronger public-source/private-runtime architecture still to be implemented.

## Pointers

- [`../ROADMAP.md`](../ROADMAP.md) explains current priorities and non-goals.
- [GitHub Issues](https://github.com/fairchild/dotfiles/issues) is the authoritative backlog.

## Lineage

The structure draws from Wiseberg's *config-of-theseus* for whitelist tracking and incremental replacement, dotpi for base-plus-local runtime composition, and dotclaude for a separate deployed clone. The public repository favors ideas that remain understandable and reusable without access to Michael's private environment.
