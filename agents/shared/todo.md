# Release Versioning Fix Handoff

## Goal

Prevent the release pipeline from publishing a mismatched DMG filename like:

- tag: `v0.3.0`
- asset: `WorkspaceManager-0.2.0.dmg`

This already happened once. The fix is implemented locally but not committed from the current worktree yet.

## Root Cause

There were two gaps:

1. The repo release workflow trusted `CFBundleShortVersionString` from `Sources/WorkspaceManager/Resources/Info.plist`, and that file had been left at `0.2.0`.
2. The local `release` skill would happily create a release tag without validating the repo's app version metadata first.

So the tag and GitHub release said `v0.3.0`, but the built app bundle still reported `0.2.0`, which flowed through to the notarized DMG filename.

## Repo Changes Ready To Commit

Repo:
- `/Users/fairchild/.codex/worktrees/2b51/workspaces`

Changed files in the repo for this fix:

- `/Users/fairchild/.codex/worktrees/2b51/workspaces/scripts/release-version.sh`
  - new helper script
  - source of truth for reading/setting/asserting app release version metadata
- `/Users/fairchild/.codex/worktrees/2b51/workspaces/.github/workflows/release.yml`
  - validates tag-driven releases with `./scripts/release-version.sh assert-tag-match`
  - reads version/build from the helper instead of duplicating plist parsing logic
- `/Users/fairchild/.codex/worktrees/2b51/workspaces/RELEASING.md`
  - docs updated to use `scripts/release-version.sh` instead of hand-editing `Info.plist`
  - stale `0.2.0` examples updated
- `/Users/fairchild/.codex/worktrees/2b51/workspaces/scripts/README.md`
  - notes the new release helper
- `/Users/fairchild/.codex/worktrees/2b51/workspaces/Sources/WorkspaceManager/Resources/Info.plist`
  - synced to the already-shipped release state:
    - `CFBundleShortVersionString = 0.3.0`
    - `CFBundleVersion = 5`

## Local Skill Changes Ready To Commit

Skill path:
- `/Users/fairchild/.agents/skills/release/scripts`

Changed files outside the repo:

- `/Users/fairchild/.agents/skills/release/scripts/analyze.ts`
  - detects repo version metadata via `scripts/release-version.sh print-tag` when present
  - prints `Repo version source: ...`
  - warns if the repo version source and suggested release version diverge
  - treats zero-commit analysis as "no new release" instead of silently bumping
- `/Users/fairchild/.agents/skills/release/scripts/release.ts`
  - checks the target release worktree's repo version metadata before tagging
  - refuses to release when repo metadata and requested version differ
  - refuses to create a release when there are no commits since the last tag
  - improved error coercion so failures show a useful message

## Verification Already Run

Repo checks:

- `bash -n scripts/release-version.sh`
- `./scripts/release-version.sh print` -> `0.3.0`
- `./scripts/release-version.sh print-build` -> `5`
- `./scripts/release-version.sh print-tag` -> `v0.3.0`
- `./scripts/release-version.sh assert-tag-match v0.3.0` -> passes
- mismatch probe against a temp plist fails with:
  - `release-version.sh: Tag/version mismatch: tag=v0.3.0 Info.plist=v0.3.1`
- `swift build` -> passed

Skill checks:

- `bun /Users/fairchild/.agents/skills/release/scripts/analyze.ts`
  - now prints `Repo version source: v0.3.0`
- `bun /Users/fairchild/.agents/skills/release/scripts/release.ts --skip-ci --no-changelog`
  - with no new commits: fails with
  - `No commits since the last release. Refusing to create a new tag.`
- `bun /Users/fairchild/.agents/skills/release/scripts/release.ts --version v0.3.1 --skip-ci --no-changelog`
  - fails with
  - `Repo version metadata is v0.3.0, but release is v0.3.1. Update app version metadata before tagging.`

## Suggested Commit Plan

Commit the repo changes separately from the skill changes.

Suggested repo commit:
- `fix: harden release version validation`

Suggested skill commit:
- `fix: validate repo version metadata before release`

## Note

The current repo worktree also has unrelated uncommitted blog files:

- `/Users/fairchild/.codex/worktrees/2b51/workspaces/blog/README.md`
- `/Users/fairchild/.codex/worktrees/2b51/workspaces/blog/2026-03-10-redesigning-the-main-window.md`
- `/Users/fairchild/.codex/worktrees/2b51/workspaces/blog/assets/2026-03-10-before-main-window.jpg`

Do not mix those into the release-versioning commit unless explicitly intended.
