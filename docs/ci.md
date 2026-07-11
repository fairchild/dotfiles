# Repository CI contract

The required pull-request checks separate two concerns:

- `public-safety` scans commit history with checksum-pinned Gitleaks and applies the repository-specific publication policy to every change.
- `Repository contract` runs deterministic installer, completeness, policy, runtime, Git-boundary, sync, and isolated-doctor fixtures when a load-bearing public path changes.

The repository-contract job downloads only the mise binary pinned in [`../install/pins.toml`](../install/pins.toml), verifies its SHA-256 checksum, and uses the checked-in task interface. It does not read private overlays, API keys, an existing home directory, model services, or mutable generated runtime. The doctor fixture creates a temporary HOME and restores first-party skills only; the separate clean-bootstrap matrix proves the pinned third-party materialization path.

## Local reproduction

Run the complete deterministic contract:

```sh
mise run check:ci
```

The component commands are also available when narrowing a failure:

```sh
mise run check:public
mise run check:safety
mise run check:completeness
mise run test:safety
mise run test:completeness
mise run test:agent-runtime
mise run test:git-runtime
mise run test:sync
./scripts/test-ci-doctor.sh
```

The Gitleaks history scan is documented separately in [`public-safety.md`](public-safety.md) because it requires the pinned Gitleaks binary and a Git range.

## Reusable workflow boundary

This workflow is intentionally repository-local. A versioned reusable participant workflow should be designed only after dotpi and dotclaude expose stable equivalent task contracts; until then, copying this interface would make unsettled assumptions a compatibility promise. That follow-up is tracked in [#32](https://github.com/fairchild/dotfiles/issues/32).
