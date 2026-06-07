# dotfiles

Umbrella for Michael's config-as-code constellation: [dotclaude](https://github.com/fairchild/dotclaude), [dotpi](https://github.com/fairchild/dotpi), [dotcursor](https://github.com/fairchild/dotcursor), and this repo. One CLI (`dotfiles`, plus an LLM-persona alias `dotty`) discovers participants, runs cross-repo health checks, and emits its own policy as an [agentskills.io](https://agentskills.io)-compatible skill so any agent picks up house rules automatically.

Lives canonically at `~/.config/dotfiles/`. A symlink at `~/code/dotfiles` keeps ergonomic parity with the sibling repos.

For what's next, see [`ROADMAP.md`](ROADMAP.md). For house rules and invariants, see [`docs/policy.md`](docs/policy.md).

## install

```sh
curl -fsSL https://raw.githubusercontent.com/fairchild/dotfiles/main/install.sh | sh
```

The installer detects OS + arch, picks a profile (`mac-personal`, `linux-personal`, `codespace`, `cloud-vm`), downloads a pinned [mise](https://mise.jdx.dev) build with SHA256 verification, clones this repo, and hands off to `mise run bootstrap`. mise then runs `home/`-symlinking, shared `~/.agents` symlinking, profile Brewfile, and agent install tasks.

It will probably break on a platform we haven't smoke-tested yet. File an issue.

## dotfiles

The policy in 30 seconds — the long form lives in [`docs/policy.md`](docs/policy.md).

The repo is the ship; the planks are the configs. We replace planks one at a time, never the keel. The keel is a small set of invariants:

- **`~/.claude` is always an independent clone on `main`.** Never a worktree, never a symlink. The reason is that hooks fire on every Claude session and a borrowed `.git` corrupts both ends.
- **Whitelist `.gitignore`s.** Anything not explicitly opted in doesn't ride along. Turns the question from *what's noisy?* into *what's intentional?*.
- **Tiered participation.** Any git repo is usable at tier 0. A `.mise.toml` lifts it to tier 1. A `[env] DOTFILES_NAME` line takes it to tier 2. A `doctor` and `bootstrap` task makes it a full tier 3 participant. No central manifest — repos declare themselves.
- **Pin everything we don't control.** Supply chain over convenience. mise is pinned with SHA256 verification; an Actions workflow opens PRs to bump it. Brewfiles are next.
- **`dotfiles` is deterministic; `dotty` is agentic.** The CLI runs in hooks and CI without an API key. The `dotty` persona shells out to `pi` for cross-repo audits when there's a human in the loop.

### participants

| Repo | Role | Runtime path |
|---|---|---|
| [dotclaude](https://github.com/fairchild/dotclaude) | Claude Code config (skills, agents, hooks) | `~/.claude` |
| [dotpi](https://github.com/fairchild/dotpi) | `pi` agent runtime config | `~/.pi/agent` |
| [dotcursor](https://github.com/fairchild/dotcursor) | Cursor IDE config | `~/.cursor` |
| dotfiles (this repo) | Shell, git, brew, shared `~/.agents` assets, the CLI itself | `$HOME` (selected fragments) |

### CLI

```
dotfiles doctor              # cross-repo health check, table output
dotfiles doctor --json       # same, JSON
dotfiles --skill             # emit SKILL.md to stdout
dotfiles --skill --install   # write to ~/.claude/skills/dotfiles/SKILL.md
dotfiles join <path>         # scaffold a participant repo
dotfiles add <name> <path>   # register an external repo
dotfiles pins                # current vs upstream lag
dotty doctor                 # persona output (more opinionated)
dotty audit                  # `pi`-backed cross-repo audit (Dr. Dotty)
```

## layout

```
~/.config/dotfiles/
├── bin/                  compiled binary (downloaded at install or built locally)
├── src/                  TypeScript source (bun)
├── scripts/              bash scripts; public ones carry #MISE description= header
├── home/                 files that symlink into $HOME (zsh fragments, gitconfig, Brewfiles)
├── agents/shared/        canonical `~/.agents` shared skills, prompts, references, templates
├── docs/                 policy.md, architecture.md, manifest-conventions.md
├── templates/            scaffolding for `dotfiles join`
├── install.sh            POSIX sh bootstrap (pinned mise install)
├── install/pins.toml     mise version + per-platform SHA256s
├── .github/workflows/    doctor, bootstrap-smoke, release, mise-pin updates
└── legacy/               parked planks (the dry dock)
```

## lineage

This repo started life as a fork of [mathiasbynens/dotfiles](https://github.com/mathiasbynens/dotfiles), the canonical pre-LLM-era starter. The original planks (`.bash_profile`, `.osx`, `.vim/`, the `bootstrap.sh` rsync) all live in [`legacy/`](legacy/) — preserved rather than deleted, since the ship metaphor requires a dry dock. Credit to the upstream contributors listed in [`legacy/README.original.md`](legacy/README.original.md) for the foundation. The umbrella restructure is a different shape on top of that foundation rather than a rejection of it.
