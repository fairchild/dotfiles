# Roadmap

## Intent

This repository is a public, reusable specification for Michael's working configuration. It should be useful to other people, portable into open-source-only environments, and safe to use as the source for private machine-local runtime without publishing that runtime back to Git.

GitHub Issues is the authoritative backlog. This file explains why the work is ordered the way it is.

## Principles

- Public source is intentional and reviewable; generated runtime and private overlays are not source.
- A documented command is a contract. Shipped documentation describes what exists, while planned surfaces are named as plans.
- Bootstrap and sync converge toward known state without destructively overwriting ambiguous local data.
- Mutable tools never write through deployment links into tracked public files.
- Third-party material is represented by immutable provenance, a lock, and narrow patches rather than copied runtime trees.
- Deterministic local checks come before orchestration or model-backed review.
- Participant repositories declare themselves; the umbrella does not maintain a central registry.

## Current state

The public-source/private-runtime baseline has landed. The public installer is
truthful and checksum-pinned; sync converges source and generated runtime;
doctor is read-only; mutable Git writes stay private; and CI exercises safety,
completeness, runtime migration, and supported bootstrap profiles.

The existing shell and mise commands are the product. A larger CLI is justified
only by repeated cross-repository friction, not by the existence of an older
plan.

## Next work

| Order | Issue | Decision boundary |
|---|---|---|
| 1 | [#7](https://github.com/fairchild/dotfiles/issues/7) — adopt the contract in dotcursor | Audit its mutable runtime first; migrate only with explicit ownership and backups. |
| 2 | [#2](https://github.com/fairchild/dotfiles/issues/2) — minimal cross-repo doctor/status | Start only after participant doctor contracts are stable; specify command and JSON output before choosing an implementation language. |
| 3 | [#32](https://github.com/fairchild/dotfiles/issues/32) — reusable participant CI | Publish only the orchestration proven common across dotfiles, dotpi, and dotclaude; keep repository policy local. |

These are future-quality improvements, not blockers for daily use. Prefer small
participant and diagnostic slices over building a broad umbrella CLI.

## Parked ideas

- [#9](https://github.com/fairchild/dotfiles/issues/9) — release binaries only
  after a CLI exists and packaging solves a demonstrated portability problem.
- [#8](https://github.com/fairchild/dotfiles/issues/8) — keep the advisory persona
  outside deterministic bootstrap, doctor, hooks, and required CI.

## Non-goals

- Building the broad TypeScript CLI described by the original phase-zero plan.
- Publishing static binaries.
- Adding a central participant registry.
- Invoking model-backed agents from required CI or hooks.
- Rewriting public Git history beyond a small, clearly worthwhile cleanup.

## Working from the backlog

```sh
cd ~/.config/dotfiles
mise run doctor
gh issue list --repo fairchild/dotfiles --state open
gh issue view --repo fairchild/dotfiles <number>
```

Read [`docs/policy.md`](docs/policy.md) before implementation. Treat GitHub
Issues as the executable backlog and this file as prioritization guidance.
