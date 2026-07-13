---
name: orca-finish
description: >-
  Methodically check and certify whether the current Orca-managed worktree is
  ready for manual closeout. Use for explicit $orca-finish invocations and
  requests such as "done", "finish this worktree", "close this worktree",
  "are we done?", or "is this safe to delete?". This V1 is readiness-only: it
  never closes resources, removes a worktree, or deletes branches. Treat status
  questions as strictly read-only and require explicit authorization before
  running completion checks or writing a receipt.
---

# Orca Finish

Use public `orca` as the authority for Orca identity. This V1 certifies
readiness; it never performs teardown.

## Choose the mode

- For a question such as `are we done?`, run `scripts/orca_finish.py check`.
  This is intrinsically read-only and never runs repository adapter commands.
- For `finish`, `close`, or `remove this worktree`, state the exact target and
  run `prepare` only after explicit authorization. Prepare may fetch remotes and
  run declared repository checks, then writes an external receipt.
- Treat `archive` as ambiguous because the public CLI has no reversible archive
  operation.

## Certify readiness

1. Read repository instructions and create or select a repository-policy
   adapter using `references/adapter-schema.md`. Missing policy blocks.
2. Inspect exact Orca identity; tracked, untracked, and ignored files; pushed
   feature HEAD; fresh PR, CI, review, and merge evidence; canonical-main
   cleanliness and fast-forwardability; and conditional deployment evidence.
3. Preserve unrelated work. Never stash, reset, clean, commit, push, merge,
   stop resources, remove a worktree, or delete a branch.
4. For authorized certification, run:

```sh
python3 scripts/orca_finish.py prepare \
  --target "$PWD" \
  --canonical-main /absolute/path/to/canonical-checkout \
  --receipt-dir "$HOME/.local/state/orca-finish" \
  --adapter /absolute/path/to/adapter.json \
  --pr-evidence /absolute/path/to/pr-evidence.json \
  --completion-evidence /absolute/path/to/check-evidence.json \
  --authorize finish
```

5. Require `ready: true`, read the external receipt, and report exact paths,
   SHAs, PR handles, named checks, deployment requirement, and blockers.

## Stop boundary

Do not invoke `orca terminal stop`, `orca tab close`, `orca emulator kill`, or
`orca worktree rm`. Do not claim that resources, processes, metadata, branches,
or the checkout were removed.

Current public CLI behavior is insufficient for automated safe teardown:

- emulator enumeration is not reliably worktree-scoped;
- worktree removal may delete the local feature branch;
- dirty/ignored-state checks and removal are not atomic.

Leave actual removal as a separate human-controlled action. Warn that current
`orca worktree rm` may remove the local branch. Never print a destructive
command as an automatic next step.

## Guardrails

- Support local `origin`-backed Git worktrees only.
- Reject remote Orca environments and credential-bearing origin URLs.
- Require fresh, exact repository, target, Orca, PR, CI, review, merge, and
  deployment bindings.
- Store only command digests and sanitized evidence metadata, never raw command
  output, credentials, private payloads, or command environments.
- Write receipts atomically outside target and canonical worktrees.
- Test with `scripts/test_orca_finish.py`; fixtures never touch live Orca state.
