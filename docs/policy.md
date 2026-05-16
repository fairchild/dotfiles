<!-- doc-meta { "owner": "dotfiles", "audience": "humans + agents", "freshness-window": "90d" } -->

# Policy

The constitution for `~/.config/dotfiles` and its participants. The umbrella CLI emits the section between the skill markers below as an [agentskills.io](https://agentskills.io)-compatible skill so any agent (Claude, Cursor, `pi`) operating in the constellation picks up house rules without a human pasting them in.

The keel never moves. Planks come and go.

<!-- skill:start -->
---
name: dotfiles
description: House policy for Michael's dot* config constellation. Read before editing dotclaude, dotpi, dotcursor, or this repo.
type: skill
version: 0.1
---

## What this is

`~/.config/dotfiles` is an umbrella that coordinates four config repos via a single CLI. It does **not** own their content; each participant repo declares itself by dropping a `.mise.toml` at its root with a `[env] DOTFILES_NAME` line. The umbrella discovers participants, runs cross-repo health checks (`dotfiles doctor`), and scaffolds new ones (`dotfiles join`).

## Invariants (the keel)

These do not move. Breaking one is an incident, not a chore.

1. **`~/.claude` is always an independent git clone on `main`.** Never a worktree, never a symlink to another path, never a branch other than `main`. The dotclaude `SessionStart` hook fast-forwards it on every session — a borrowed `.git` corrupts both ends. Worktrees go in `~/.worktrees/`.
2. **Whitelist `.gitignore`s.** Every dot* repo ignores everything by default and opts back in. The question is "what's intentional?", not "what's noisy?".
3. **Tiered participation, not central registration.** A repo declares itself; the umbrella discovers it. There is no central manifest file the umbrella owns.
   - **T0**: any git repo. Generic doctor still runs (clean tree, README/LICENSE present, no obvious secrets).
   - **T1**: `.mise.toml` exists. Convention shim picks up `doctor`/`check`/`health`/`verify`/`test` task if present.
   - **T2**: `.mise.toml` has `[env] DOTFILES_NAME = "..."` block. Repo shows up by name in the participant table.
   - **T3**: tasks `doctor` and `bootstrap` are defined and runnable. Full participant.
4. **Pinned upstream, never `latest`.** mise version + SHA256 pinned in `install/pins.toml`. A weekly Actions cron opens a PR to bump the pin; CI smoke tests must pass before merge. Same pattern coming for Brewfiles.
5. **Two personas, one binary.** `dotfiles` is deterministic — runs in hooks and CI, no API key, no agent shells. `dotty` is the same binary invoked under a persona alias; it can shell out to `pi` for cross-repo audits when a human is in the loop. CI and hooks never invoke `dotty`.

## Conventions

- **Task names** (mise): `doctor`, `bootstrap`, `fix`, `audit`, `sync`, `clean`, `install:*`. The convention shim falls through `doctor → check → health → verify → test → :default-generic` when a participant has no `doctor` task yet.
- **Public scripts** carry `#MISE description="..."` as the second line so they surface in `mise tasks ls`. Private helpers live in `scripts/lib/` or use `_` prefix and never carry the header.
- **Repo identity** lives in `[env]` of `.mise.toml`:
  ```toml
  [env]
  DOTFILES_NAME = "dotpi"
  DOTFILES_RUNTIME = "~/.pi/agent"
  ```
  No separate manifest file. No discovery beyond filesystem walk + `[env]` parse.
- **Profiles** via mise: `.mise.<profile>.toml` activated by `MISE_ENV`. Active profiles: `mac-personal`, `linux-personal`, `codespace`, `cloud-vm`.
- **Brewfile per profile**: `home/Brewfile`, `home/Brewfile.codespace`, `home/Brewfile.cloud-vm`. Linux uses Linuxbrew if present; otherwise prints translation table.
- **Two-clone deploy** (dotclaude pattern): dev copy at `~/code/<name>`, runtime copy at `~/<runtime-path>`. Hooks operate on runtime; commits happen in dev. The `sync` task fast-forwards runtime from origin.

## Blast-radius rules

- **`~/.claude` and `~/.config/dotfiles` are sacred.** Never auto-modify either from a hook. Hooks may run `dotfiles --skill --install` (idempotent, append-only to a known path); they may not touch `home/` or anything in dotclaude that isn't already symlinked.
- **The installer is a one-way door.** `curl … | sh` clones to `~/.config/dotfiles` if absent and exits if present. It never updates an existing clone — that's `mise run sync`.
- **`--fix` defaults to interactive.** `--non-interactive` flag applies all proposed fixes. Hooks and CI must use `--non-interactive` explicitly; default behavior is conservative.
- **Dr. Dotty is advisory.** She comments on PRs and produces audit reports. She never opens commits, never pushes, never edits files in CI. The only writes she's authorized for are the audit artifact in `tmp/dr-dotty/<run-id>.md`.

## Anti-conventions (load-bearing don'ts)

- Don't put a manifest file at the umbrella that lists participants. Use filesystem discovery + `[env]` blocks. Repos declare themselves.
- Don't shell out to `pi` from anything except `dotty` subcommands and the `dr-dotty-review` workflow. Hooks and `doctor` must remain network-free.
- Don't add planks directly to `$HOME`. Add them under `home/` and let `install:zsh` (or equivalent) symlink them. The repo is the source of truth; `$HOME` is the deployment.
- Don't delete legacy planks. Move them to `legacy/`. The dry dock is part of the design.

## When to invoke the persona

- `dotfiles` for: hooks, CI checks, scripted bootstrap, doctor, skill emission, scaffolding. Anything deterministic.
- `dotty` for: ad-hoc cross-repo audits, reasoning about plank tradeoffs, PR review prose, "why did this drift?" forensics. Anything that benefits from a model on top.

If you're unsure which to call, the answer is `dotfiles`. The persona unlocks more aggressive output; the deterministic surface is always sufficient for verification.

<!-- skill:end -->

## Pointers

- [`../ROADMAP.md`](../ROADMAP.md) — priority-ordered open work, organized by GitHub milestone.
- [GitHub Issues](https://github.com/fairchild/dotfiles/issues) — authoritative backlog.

## Lineage

The structure draws from [Wiseberg's *config-of-theseus*](https://shift1w.com/blog/config-of-theseus/) for the whitelist `.gitignore` + plank-replacement frame, [dotpi](https://github.com/fairchild/dotpi) for the layered base+local→runtime split, [dotclaude](https://github.com/fairchild/dotclaude) for the two-clone deploy, and [the-library](https://github.com/disler/the-library) for the catalog-of-references pattern that keeps the umbrella thin.

The article that started this is honest about a key point we keep: it will probably break on a platform we haven't tested. The bootstrap-smoke matrix CI is the receipt for that promise, not a denial of it.
