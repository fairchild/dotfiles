# Risk Assessment Guidelines

Score each package update 1-5 based on breaking change likelihood.

## Risk Levels

### 1 - Minimal Risk
- Patch versions (x.y.Z)
- Security patches
- Type definition updates (@types/*, types-*)
- Documentation-only changes

### 2 - Low Risk
- Minor versions with only "Added" sections
- Bug fixes with no API changes
- Performance improvements
- New optional features

### 3 - Moderate Risk
- Minor versions with deprecation warnings
- Changes to peer dependencies
- New required configuration options
- Default behavior changes (documented)

### 4 - High Risk
- Major version bumps
- Changelog mentions "BREAKING", "migration", "removed"
- API signature changes
- Peer dependency major bumps

### 5 - Critical Risk
- Major rewrites or architecture changes
- No changelog available
- Maintainer change
- Known issues in GitHub discussions

## Quick Assessment Checklist

1. Is it a patch? → Risk 1
2. Is it a minor with "Added" only? → Risk 2
3. Does changelog mention "breaking"? → Risk 4+
4. Is it a build tool or framework? → Risk 3+
5. No changelog available? → Risk 5

## Ecosystem-Specific Notes

### JavaScript/TypeScript
- React major versions → Risk 5 (concurrent features, API changes)
- TypeScript major → Risk 4 (stricter checks)
- Build tools (Vite, esbuild) → Risk 3+
- UI libraries (Radix, shadcn) → Usually Risk 2

### Python
- Django/FastAPI major → Risk 4-5
- SQLAlchemy major → Risk 5 (ORM changes)
- pytest major → Risk 3
- Type checkers (mypy) → Risk 3

### Rust
- Tokio major → Risk 5
- Serde minor → Usually Risk 1-2
- Web frameworks → Risk 3-4

## Changelog Sources

```bash
# npm - get repo URL
npm view <package> repository.url

# Then fetch releases
gh api repos/{owner}/{repo}/releases --jq '.[0:5] | .[] | .tag_name + ": " + .name'
```

For Python, check PyPI or GitHub releases.
For Rust, check crates.io or GitHub releases.

## Using History

Before scoring, check if we've updated this before:

```bash
grep "<package>" ~/.claude/skills/update-dependencies/data/outcomes.jsonl
```

Past `required_migration` outcomes → increase risk score.
