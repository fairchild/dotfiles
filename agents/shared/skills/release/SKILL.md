---
name: release
description: Create semantic versioned releases with AI-generated changelogs. Worktree-aware - works from any branch. Use when the user wants to create a release, cut a release, bump version, or publish a new version. Supports dry-run preview, pre-releases (alpha/beta/rc), and CI status checks.
license: Apache-2.0
disable-model-invocation: true
---

# Release

Create semantic versioned releases from any branch or worktree.

## Quick Start

```bash
# Preview release (no changes)
bun ~/.claude/skills/release/scripts/analyze.ts

# Execute release
bun ~/.claude/skills/release/scripts/release.ts

# Dry run
bun ~/.claude/skills/release/scripts/release.ts --dry-run
```

## Command Options

| Option | Effect |
|--------|--------|
| no args | Analyze, confirm, release origin/main |
| --dry-run | Preview only, no changes |
| --version vX.Y.Z | Override suggested version |
| --no-changelog | Skip CHANGELOG.md, notes in GitHub release only |
| --current-branch | Release HEAD of current branch, for hotfix branches |
| --prerelease alpha | Create pre-release, e.g. v1.0.0-alpha.1 |
| --skip-ci | Skip CI status check |

## Worktree-Aware Workflow

The skill releases `origin/main` regardless of your current branch:

```
You're in:     ~/conductor/workspaces/.claude/casablanca (worktree)
Current branch: feat/my-feature
Release target: origin/main ✓
```

**How it works:**

- Creates ephemeral worktree at `~/.worktrees/<repo>/release-<tag>`
- Commits changelog, tags, pushes to origin/main
- Cleans up worktree after release

This approach is predictable and never modifies your current working directory. Use `--current-branch` to release from current directory instead (for hotfix branches).

## Workflow

### 1. Analyze

Run the analyze script (read-only, safe anytime):

```bash
bun ~/.claude/skills/release/scripts/analyze.ts
```

Shows:
- Current context (branch, worktree status)
- Target branch (origin/main)
- Commits since last tag
- Suggested version
- Generated changelog
- CI status

### 2. Review and Confirm

Check the suggested version and changelog preview. Adjust with:
- `--version vX.Y.Z` to override version
- `--prerelease alpha` for alpha/beta/rc

### 3. Execute

```bash
bun ~/.claude/skills/release/scripts/release.ts
```

The script:
1. Checks CI status (fail if broken, unless `--skip-ci`)
2. Finds or creates release worktree
3. Updates CHANGELOG.md (unless `--no-changelog`)
4. Commits: `release: vX.Y.Z`
5. Creates and pushes tag
6. Creates GitHub release
7. Cleans up ephemeral worktree

## Version Bumping

| Change Type | Bump | Example |
|-------------|------|---------|
| Breaking changes | Major | 1.2.3 → 2.0.0 |
| feat commits | Minor | 1.2.3 → 1.3.0 |
| fix, chore, etc. | Patch | 1.2.3 → 1.2.4 |

Pre-1.0: Breaking → minor, feat → minor, fix → patch.

Pre-releases: --prerelease alpha → v1.0.0-alpha.1, v1.0.0-alpha.2, etc.

## Changelog Format

Uses [Keep a Changelog](https://keepachangelog.com/):

```markdown
## [1.3.0] - 2026-01-24

### Added
- feature: New capability

### Fixed
- bug: Resolved issue

### Changed
- refactor: Improved performance
```

## Error Recovery

See [references/troubleshooting.md](references/troubleshooting.md) for:
- Partial failure recovery (commit/push/release)
- Undoing a release (delete tag, retract)
- Worktree cleanup
- CI issues

Quick fixes:
```bash
# Push failed after commit
git push origin main --tags

# GitHub release failed after push
gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes

# Delete bad release
gh release delete vX.Y.Z --yes --cleanup-tag
```
