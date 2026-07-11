# Public-tree safety

The repository is public, so publication safety is a local and pull-request gate rather than a review-time hope. The checks are deliberately redundant: Gitleaks detects known and generic secret shapes in commits, while the repository-specific gate rejects private paths and artifacts that are not necessarily credentials.

## Local reproduction

Run the deterministic repository checks:

```sh
mise run check:safety
mise run test:safety
mise run check:gitleaks
```

To reproduce the pull-request size calculation:

```sh
./scripts/check-public-safety.sh --base origin/master --head HEAD
gitleaks git --redact --config .gitleaks.toml --log-opts='origin/master..HEAD'
```

Gitleaks is pinned under `[gitleaks]` in [`../install/pins.toml`](../install/pins.toml). CI downloads the open-source release archive and verifies its SHA-256 checksum before scanning.

## What is rejected

- Private-key files and private-key content.
- Credential-shaped literal assignments. Environment lookups and explicit placeholders are not treated as credentials.
- `/Users/<name>/` and `/home/<name>/` paths under public agent assets unless the exact fixture path is documented in [`../scripts/public-safety-allowlist.txt`](../scripts/public-safety-allowlist.txt).
- JSONL histories, logs, handoffs, internal todo files, plugin cache manifests, and generated/runtime directory contents.
- Materialized `agents/shared/skills/` content; third-party skills belong in the immutable lock.
- Incomplete third-party lock entries, unattributed patches, and vendored directories without a license and immutable provenance.
- Pull requests over 150 files, 20,000 added lines, or 30,000 changed lines without maintainer approval.

## Overrides

Secret, private-key, runtime-artifact, and provenance findings have no CI bypass. Fix the source or add a narrowly reviewed exact-path/regex allowlist entry with a public explanation.

The size gate is different: a large intentional public import can be legitimate. A maintainer may add the `large-public-change-approved` label after reviewing the file inventory and recording why the change must be atomic in the PR body. For local reproduction only, set `PUBLIC_SAFETY_LARGE_PR_APPROVED=1`.

An override does not make content safe; it records that a maintainer evaluated a mechanical size threshold. Gitleaks and all content gates still run.
