# Grouping Strategies

Group related packages for batched updates. Fewer PRs, less noise.

## General Principles

1. **Related packages together** - They often have version dependencies
2. **Security first** - Own PR for quick merge
3. **Major versions separate** - Individual attention for breaking changes
4. **Patches batch freely** - Low risk, batch many

## Risk-Based Groups

### Security Fixes (Own PR)
Always separate:
- Critical/High severity vulnerabilities
- Title: `deps(security): fix N vulnerabilities`

### Low-Risk Batch
Combine into single PR:
- All patch updates (x.y.Z)
- Minor updates with "Added" only changelogs
- Type packages (@types/*, types-*)
- Title: `deps(patch): batch N packages`

### Individual Updates
Each gets own PR:
- Framework major versions (React, Django, Tokio)
- Build tools (Vite, Cargo, uv)
- Any package with risk score >= 4
- Title: `deps(<package>): upgrade to vX`

## Ecosystem Groups

See ecosystem references for specific patterns:
- [npm.md](ecosystems/npm.md) - Radix, TanStack, React, OTEL
- [python.md](ecosystems/python.md) - Web frameworks, data science
- [cargo.md](ecosystems/cargo.md) - Async runtime, Serde, web

## Naming Convention

### Branch Names
```
deps/security-YYYYMMDD
deps/patch-batch-YYYYMMDD
deps/<ecosystem>-batch-YYYYMMDD
deps/<package>-upgrade-YYYYMMDD
```

### Commit Messages
```
deps(security): fix N vulnerabilities
deps(patch): batch update N packages
deps(radix): update N components
deps(react): upgrade to v19
```

## Dependency Chain Detection

When package A depends on package B, update together:

```bash
# npm - check peer dependencies
npm view <package> peerDependencies

# Check if packages share a dependency
npm ls <shared-dep>
```

Common chains:
- `react` + `react-dom` + `@types/react`
- `vite` + `@vitejs/plugin-react`
- `fastapi` + `starlette` + `uvicorn`
- `tokio` + `tokio-*`

## Priority Order

1. Security fixes (merge first)
2. Ecosystem batches (group related)
3. Low-risk patches (batch together)
4. Individual major updates (careful review)
