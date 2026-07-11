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

## Current focus

[Milestone 1 — Next release: public source → private runtime](https://github.com/fairchild/dotfiles/milestone/1) makes the repository truthful, safe, and reproducible before adding a larger product layer.

Done means the public install command works on supported clean environments; tracked source cannot silently absorb generated or private state; sync updates source, materializes runtime, and runs doctor; CI checks safety, completeness, and bootstrap behavior; and dotpi plus dotclaude demonstrate the same source/runtime contract.

The TypeScript CLI is deliberately not a requirement for this release. The existing shell and mise surfaces are enough to prove the architecture first.

## Next release work order

| Order | Issue | Outcome |
|---|---|---|
| 1 | [#19](https://github.com/fairchild/dotfiles/issues/19) — restore a truthful public bootstrap entrypoint | Fix the `main`/`master` mismatch and stop presenting planned surfaces as shipped. |
| 2 | [#11](https://github.com/fairchild/dotfiles/issues/11) — repair mise pin verification | Restore the weekly verified update path before the pin drifts further. |
| 3 | [#16](https://github.com/fairchild/dotfiles/issues/16) — gate the public tree | Prevent secrets, runtime artifacts, unmanaged vendor trees, and unexpectedly large changes from reaching the public repository. |
| 4 | [#20](https://github.com/fairchild/dotfiles/issues/20) — define the source/runtime contract | Give installers, doctor checks, and participant repos one ownership model. |
| 5 | [#13](https://github.com/fairchild/dotfiles/issues/13) — stop mutable Git writes reaching public source | Fix the known direct-write path through `~/.gitconfig`. |
| 6 | [#21](https://github.com/fairchild/dotfiles/issues/21) — make sync converge | Fast-forward source, materialize runtime, and run doctor as one idempotent operation. |
| 7 | [#12](https://github.com/fairchild/dotfiles/issues/12) — detect repository completeness gaps | Catch intended public files that whitelist ignore rules silently omit. |
| 8 | [#4](https://github.com/fairchild/dotfiles/issues/4) — verify clean bootstrap | Exercise real supported platform/profile pairs in an isolated environment. |
| 9 | [#3](https://github.com/fairchild/dotfiles/issues/3) — require repo-local checks | Run the deterministic safety, completeness, and doctor checks on pull requests. |
| 10 | [#5](https://github.com/fairchild/dotfiles/issues/5) and [#6](https://github.com/fairchild/dotfiles/issues/6) — prove participant adoption | Apply the settled contract to dotpi and dotclaude without depending on the future CLI. |

## Future priorities

1. **Cross-repo orchestration** — [Milestone 2](https://github.com/fairchild/dotfiles/milestone/2) starts with a minimal deterministic doctor/status aggregator in [#2](https://github.com/fairchild/dotfiles/issues/2), after participant contracts are stable.
2. **Remaining participant adoption** — [#7](https://github.com/fairchild/dotfiles/issues/7) brings dotcursor into the established model after its mutable runtime has been audited.
3. **Release packaging** — [#9](https://github.com/fairchild/dotfiles/issues/9) remains an unmilestoned idea until a CLI exists and a binary solves a demonstrated portability problem.
4. **Advisory persona** — [#8](https://github.com/fairchild/dotfiles/issues/8) remains an unmilestoned idea; model-backed review is not part of the deterministic configuration contract.

## Non-goals for the next release

- Building the broad TypeScript CLI described by the original phase-zero plan.
- Publishing static binaries.
- Adding a central participant registry.
- Invoking model-backed agents from required CI or hooks.
- Onboarding dotcursor before the source/runtime pattern is proven elsewhere.
- Rewriting public Git history beyond a small, clearly worthwhile cleanup.

## Working from the backlog

```sh
cd ~/.config/dotfiles
mise run doctor
gh issue list --repo fairchild/dotfiles --milestone "Next release: public source → private runtime"
gh issue view --repo fairchild/dotfiles <number>
```

Read [`docs/policy.md`](docs/policy.md) before implementation. Where the policy still describes planned CLI behavior as current, [#19](https://github.com/fairchild/dotfiles/issues/19) is the correction surface rather than permission to build the plan implicitly.
