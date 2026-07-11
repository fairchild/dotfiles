# Sync convergence

`mise run sync` converges public source and generated runtime. It is intentionally stricter than `git pull`: a deployed configuration checkout should match its public remote, not carry unpublished work.

## Sequence

1. Require the configured branch and a clean tracked working tree.
2. Fetch and inspect the remote-tracking branch.
3. Refuse local-ahead or diverged history; fast-forward only when behind.
4. Run the non-destructive agent installer, which links first-party source and restores pinned third-party runtime.
5. Run doctor and return its exact exit status.

Private overlays and unknown runtime are not reset. The installer preserves unclassified collisions in timestamped backups as defined by [`source-runtime-contract.md`](source-runtime-contract.md).

## Modes

```sh
mise run sync
./scripts/sync.sh --first-party-only
./scripts/sync.sh --offline
```

`--first-party-only` fetches public source but skips network restoration of third-party skills. `--offline` performs no fetch, uses the existing `origin/master` tracking ref, and implies first-party-only materialization. Offline mode fails when no tracking ref exists; it does not guess which local commit should be authoritative.

## Failure recovery

- **Dirty source:** commit intentional public work in a development checkout, or move/discard it explicitly.
- **Ahead source:** publish or move the local commits; sync will not pretend an unpublished deployment is converged.
- **Diverged source:** reconcile in a development checkout, then fast-forward the deployed checkout.
- **Fetch failure:** restore network access or use `--offline` only when the existing tracking ref is known to be sufficient.
- **Materialization failure:** runtime is not declared healthy and doctor is not run.
- **Doctor warning/failure:** sync returns the same nonzero status so callers cannot mistake partial convergence for health.

Bootstrap creates a missing installation. The `install:*` tasks repair one owned surface. Sync updates an existing installation across source, generated runtime, and health verification.
