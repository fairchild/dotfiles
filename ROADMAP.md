# Roadmap

Phase 0 (umbrella + daily-use install) shipped 2026-05-10 via [PR #1](https://github.com/fairchild/dotfiles/pull/1). Daily-driver dotfiles are live: `~/.zshrc` and `~/.gitconfig` symlink into this repo; `mise run doctor` is the canonical health check.

This file is the priority-ordered view over open issues. The authoritative backlog lives at https://github.com/fairchild/dotfiles/issues, organized into milestones:

- [Milestone 1 — Phase 1: orchestration + CI](https://github.com/fairchild/dotfiles/milestone/1)
- [Milestone 2 — Phase 2: cursor onboarding + polish](https://github.com/fairchild/dotfiles/milestone/2)

## Phase 1 — orchestration + CI

Turn the umbrella from "working solo on this Mac" into "monitored + cross-repo aware". End state: `dotfiles doctor` returns OK across all three personal config repos.

| # | Issue | Why now |
|---|---|---|
| 1 | [#11](https://github.com/fairchild/dotfiles/issues/11) — fix `update-mise-pin.yml` GPG key URL | Small; restores weekly auto-bump |
| 2 | [#2](https://github.com/fairchild/dotfiles/issues/2) — TypeScript CLI (`dotfiles doctor` / `--skill` / `join` / `add` / `pins`) | Half-day; unblocks Phase 2 issues #8, #9, #10 |
| 3 | [#4](https://github.com/fairchild/dotfiles/issues/4) — `bootstrap-smoke.yml` matrix workflow | High signal, low ongoing cost; catches Codespace bootstrap regressions weekly |
| 4 | [#3](https://github.com/fairchild/dotfiles/issues/3) — `doctor.yml` + `doctor-reusable.yml` | PR-time check + reusable callable for participant repos |
| 5 | [#5](https://github.com/fairchild/dotfiles/issues/5) — onboard dotpi as T3 participant | Compounds value with #2 |
| 6 | [#6](https://github.com/fairchild/dotfiles/issues/6) — onboard dotclaude as T3 participant | Same shape as #5 |

## Phase 2 — cursor onboarding + polish

Final participant onboarded and quality-of-life polish. End state: the constellation is fully self-orchestrating; the CLI ships as a static binary on tagged releases.

| # | Issue | Notes |
|---|---|---|
| 1 | [#7](https://github.com/fairchild/dotfiles/issues/7) — onboard dotcursor | Needs `git clone … ~/code/dotcursor` first; independent of Phase 1 |
| 2 | [#9](https://github.com/fairchild/dotfiles/issues/9) — `release.yml` (binary publish on tag) | Small; depends on Phase 1 #2 |
| 3 | [#8](https://github.com/fairchild/dotfiles/issues/8) — Dr. Dotty LLM persona + skill auto-install | Medium; depends on Phase 1 #2 |
| 4 | [#10](https://github.com/fairchild/dotfiles/issues/10) — `dr-dotty-review.yml` advisory PR comments | Depends on #8 |

## How to pick up the work

```sh
cd ~/.config/dotfiles
mise run doctor                                                     # confirm install is healthy
gh issue list --milestone "Phase 1: orchestration + CI"             # see the queue
gh issue view <N>                                                   # detail for a specific issue
```

Read [`docs/policy.md`](docs/policy.md) before opening a PR — it documents the invariants (the keel) that must not move.

## Beyond Phase 2 (no issues filed yet)

Listed for completeness from the original phase-0 plan; not yet broken into issues:

- `dotfiles audit` deep cross-repo synthesis (post-Phase-2)
- `dotty pins audit` PR evaluation via pi
- `dotfiles status --remote` cross-repo CI rollup via `gh api`
- Last-touched / deprecated-plank reporting (`dotfiles audit --stale`)
- `attic/` removal-graveyard convention (currently `legacy/` serves the dry-dock role)
- Brewfile pinning + auto-update (mirror of mise pin pattern)
- `dotfiles --skill` live-templating beyond the `## Detected` section
- Cross-repo PR triage / batch operations
- Webui dashboard (visualizer for the constellation)
- A `dotwork` for work configs joining via `dotfiles join`

File issues when any of these get concrete.
