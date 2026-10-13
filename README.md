# dotfiles

Public source for Michael's shell, Git, Homebrew, and shared agent configuration, plus the conventions used by [dotclaude](https://github.com/fairchild/dotclaude) and two private configuration repositories, for Pi and for Cursor.

The repository is deliberately public so useful configuration and agent patterns can be copied, forked, and reused in open-source-only environments. Machine-local identity, secrets, generated runtime, logs, and caches do not belong in the tracked source.

The canonical checkout lives at `~/.config/dotfiles/`. A symlink at `~/code/dotfiles` is optional local convenience.

## Install

> [!WARNING]
> This command installs Michael's opinionated shell, Git, agent, and package
> configuration. It is intended for his machines and for reviewed forks, not
> as a generic dotfiles installer. Review `home/Brewfile`, `.mise.toml`, and the
> install scripts before running it on another machine.

```sh
curl -fsSL https://raw.githubusercontent.com/fairchild/dotfiles/master/install.sh | sh
```

The installer detects the operating system and architecture, downloads the mise version pinned in [`install/pins.toml`](install/pins.toml), verifies its SHA-256 checksum, clones this repository, and runs `mise run bootstrap`.

It currently supports macOS and Linux on x86-64 and arm64. Forking and adapting
the personal package lists is expected.

## Shipped commands

The current interface is mise plus small shell scripts:

```sh
mise run bootstrap         # install shell, Git, agent, and package configuration
mise run doctor            # inspect the current installation without repairing it
mise run sync              # fast-forward source, rematerialize runtime, run doctor
mise run install:zsh
mise run install:git
mise run install:agents
mise run install:skills
mise run install:brew
mise run check:public      # verify public entrypoints and a fixture bootstrap
mise run check:safety      # reject secrets, private runtime, and unsafe vendoring
mise run check:completeness # reject omitted entrypoints and broken local references
mise run test:safety       # exercise positive and negative safety fixtures
mise run check:ci          # reproduce deterministic pull-request checks
```

The broader `dotfiles`/`dotty` CLI described in earlier plans has not shipped. A smaller future orchestration surface is tracked in [#2](https://github.com/fairchild/dotfiles/issues/2); it is not required for the current release.

## Architecture

Git source is reviewed, mise tasks materialize runtime, and `doctor` checks the
result without repairing it:

| Layer | Public source | Runtime | Authority |
|---|---|---|---|
| Shell and Git base | `home/` | selected files under `$HOME` | Git for the base; `*.local` files for private overrides |
| First-party agent assets | `agents/shared/` | links under `~/.agents/` | Git |
| Third-party skills | lock and patches under `agents/shared/` | managed directories under `~/.agents/skills/` | immutable provenance plus installer |
| Machine-local state | examples only | identity, secrets, logs, caches, generated state | local machine or owning application |

Generated runtime stays outside the public checkout. Unknown collisions are
backed up before replacement, and mutable tools never write through links into
tracked source.

| Question | Reference |
|---|---|
| What owns a path? | [`docs/source-runtime-contract.md`](docs/source-runtime-contract.md) |
| What may be published? | [`docs/public-safety.md`](docs/public-safety.md) |
| Why is a file omitted? | [`docs/repository-completeness.md`](docs/repository-completeness.md) |
| How does update and recovery work? | [`docs/sync.md`](docs/sync.md) |
| How are PR checks reproduced? | [`docs/ci.md`](docs/ci.md) |

## Participants

| Repository | Role | Runtime path |
|---|---|---|
| [dotclaude](https://github.com/fairchild/dotclaude) | Claude Code configuration | `~/.claude` |
| Pi configuration (private) | Pi agent configuration | `~/.pi/agent` |
| Cursor configuration (private) | Cursor configuration | `~/.cursor` |
| dotfiles | Shell, Git, Homebrew, and shared agent sources | selected paths under `$HOME` |

Cross-repository health aggregation remains future work. GitHub Issues records
the executable backlog; [`ROADMAP.md`](ROADMAP.md) explains the current order.

## Layout

```text
home/                 public base configuration and package lists
agents/shared/        first-party sources, third-party lock, patches, prompts
scripts/              deterministic install, restore, doctor, and check scripts
install.sh            POSIX bootstrap entrypoint
install/pins.toml     pinned mise version, signing key, and platform checksums
docs/policy.md        current invariants and conventions
legacy/               preserved pre-umbrella configuration
```

## Lineage

This repository started as a fork of [mathiasbynens/dotfiles](https://github.com/mathiasbynens/dotfiles). The original configuration remains under [`legacy/`](legacy/), with upstream credit in [`legacy/README.original.md`](legacy/README.original.md).
