# npm/bun/pnpm Ecosystem

Commands for JavaScript/TypeScript dependency management.

## Package Manager Detection

| Lockfile | Manager | Install | Run |
|----------|---------|---------|-----|
| `bun.lock` / `bun.lockb` | bun | `bun install` | `bun run` |
| `pnpm-lock.yaml` | pnpm | `pnpm install` | `pnpm run` |
| `package-lock.json` | npm | `npm install` | `npm run` |

## Security Audit

```bash
# npm/pnpm
npm audit --json

# bun (uses npm audit under the hood)
bun pm audit
```

If `npm audit fix --dry-run` shows safe fixes, apply with `npm audit fix`.

## Outdated Analysis

```bash
# npm
npm outdated --json

# pnpm
pnpm outdated --json

# bun
bun outdated --json
```

## Update Commands

```bash
# Using npm-check-updates (works with all managers)
npx npm-check-updates@latest -u --filter "<package1>,<package2>"

# Then install
bun install  # or pnpm install, npm install
```

## Test Commands

```bash
# Common patterns
bun test
bun run check      # Type checking
bun run build      # Build verification
```

## Common Ecosystem Groups

### Radix UI
```
@radix-ui/react-*
```
Update together - shared primitives and styles.

### TanStack
```
@tanstack/react-query
@tanstack/react-table
@tanstack/react-virtual
```
Often co-released, shared conventions.

### React Core
```
react
react-dom
@types/react
@types/react-dom
```
**Always update together.**

### Build Tools
```
vite
@vitejs/plugin-react
esbuild
```
Update together for compatibility.

### OpenTelemetry
```
@opentelemetry/api
@opentelemetry/sdk-*
@opentelemetry/exporter-*
```
**Strict version alignment required.**

## Lockfile Handling

After updates, commit the appropriate lockfile:
- `bun.lock` or `bun.lockb` for bun
- `pnpm-lock.yaml` for pnpm
- `package-lock.json` for npm

```bash
git add package.json bun.lock  # adjust for your manager
```

## Dependabot Integration

If Dependabot PRs exist, consider triage mode:

```bash
# List open Dependabot PRs
gh pr list --author "app/dependabot" --json number,title,mergeable,statusCheckRollup

# Merge passing PRs
gh pr merge <number> --squash
```
