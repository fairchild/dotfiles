# Repository policy and evidence

`orca_finish.py` never executes repository checks. The agent runs required
checks under the user's authorized scope, sanitizes their results into evidence
files, then asks the script to certify those files against declarative policy.

## Policy adapter

```json
{
  "schema_version": 3,
  "name": "dotfiles",
  "required_completion_checks": ["tests", "public-safety"],
  "required_deletion_readiness_checks": [],
  "deployment": {"required": false, "reason": "setup-only change"}
}
```

For native/UI work, set deployment required and name the repository's receipt
verification checks. Non-native changes should state why deployment is not
required. The certification receipt binds the adapter SHA-256.

## PR evidence

```json
{
  "schema_version": 3,
  "provider": "github",
  "repository": "git@example.invalid:org/repo.git",
  "pr": "#123",
  "base_branch": "main",
  "state": "merged",
  "head_sha": "40-hex-feature-sha",
  "merge_sha": "40-hex-merge-or-squash-sha",
  "required_checks": [{"name": "test", "status": "success"}],
  "review_decision": "approved",
  "unresolved_threads": 0,
  "observed_at": "2026-07-12T12:00:00Z",
  "target_path": "/absolute/source/worktree",
  "orca_id": "exact-id",
  "instance_id": "exact-instance"
}
```

## Completion or deployment evidence

```json
{
  "schema_version": 3,
  "repository": "git@example.invalid:org/repo.git",
  "base_branch": "main",
  "head_sha": "40-hex-feature-sha",
  "target_path": "/absolute/source/worktree",
  "orca_id": "exact-id",
  "instance_id": "exact-instance",
  "observed_at": "2026-07-12T12:00:00Z",
  "checks": [
    {
      "name": "tests",
      "status": "success",
      "command_sha256": "64-hex-command-digest",
      "completed_at": "2026-07-12T11:59:00Z"
    }
  ]
}
```

Supply completion evidence for both modes. Supply deployment evidence only
when policy requires it. Unknown, missing, unsuccessful, older than 15 minutes,
future-dated, or mismatched evidence blocks certification. Evidence must contain
sanitized metadata only—never raw output, environments, tokens, or payloads.
