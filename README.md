# dotfiles

Public source for Michael's shell, Git, Homebrew, and shared agent configuration, plus the conventions used by [dotclaude](https://github.com/fairchild/dotclaude), [dotpi](https://github.com/fairchild/dotpi), and [dotcursor](https://github.com/fairchild/dotcursor).

The repository is deliberately public so useful configuration and agent patterns can be copied, forked, and reused in open-source-only environments. Machine-local identity, secrets, generated runtime, logs, and caches do not belong in the tracked source.

The canonical checkout lives at `~/.config/dotfiles/`. A symlink at `~/code/dotfiles` is optional local convenience.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/fairchild/dotfiles/master/install.sh | sh
```

The installer detects the operating system and architecture, downloads the mise version pinned in [`install/pins.toml`](install/pins.toml), verifies its SHA-256 checksum, clones this repository, and runs `mise run bootstrap`.

It currently supports macOS and Linux on x86-64 and arm64. The personal package lists are opinionated; forking them is expected.

## Shipped commands

The current interface is mise plus small shell scripts:

```sh
mise run bootstrap         # install shell, Git, agent, and package configuration
mise run doctor            # inspect the current installation without repairing it
mise run sync              # fast-forward the public source checkout
mise run install:zsh
mise run install:git
mise run install:agents
mise run install:skills
mise run install:brew
mise run check:public      # verify public entrypoints and a fixture bootstrap
mise run check:safety      # reject secrets, private runtime, and unsafe vendoring
mise run test:safety       # exercise positive and negative safety fixtures
```

The broader `dotfiles`/`dotty` CLI described in earlier plans has not shipped. A smaller future orchestration surface is tracked in [#2](https://github.com/fairchild/dotfiles/issues/2); it is not required for the current release.

## Source and runtime

Tracked files are public source. A real private `~/.gitconfig` loader includes the public Git base and `~/.gitconfig.local`, while the linked public zsh base includes `~/.zshrc.local`. Shared first-party skills are tracked under `agents/shared/first-party-skills/`; third-party skills are represented by an immutable lock plus local patches, then materialized during installation.

The ownership and migration rules are documented in [`docs/source-runtime-contract.md`](docs/source-runtime-contract.md). Generated shared-agent state lives in a real `~/.agents/` directory outside the public checkout; first-party source remains linked and third-party material is restored from the immutable lock.

Publication checks and the narrowly scoped override process are documented in [`docs/public-safety.md`](docs/public-safety.md).

## Participants

| Repository | Role | Runtime path |
|---|---|---|
| [dotclaude](https://github.com/fairchild/dotclaude) | Claude Code configuration | `~/.claude` |
| [dotpi](https://github.com/fairchild/dotpi) | Pi agent configuration | `~/.pi/agent` |
| [dotcursor](https://github.com/fairchild/dotcursor) | Cursor configuration | `~/.cursor` |
| dotfiles | Shell, Git, Homebrew, and shared agent sources | selected paths under `$HOME` |

Participant declarations and cross-repository health aggregation are future work. GitHub Issues records the executable plan; [`ROADMAP.md`](ROADMAP.md) explains the order.

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
