# Rust/Cargo Ecosystem

Commands for Rust dependency management.

## Security Audit

```bash
# Install cargo-audit if needed
cargo install cargo-audit

# Run audit
cargo audit --json
```

## Outdated Analysis

```bash
# Install cargo-outdated if needed
cargo install cargo-outdated

# Check outdated
cargo outdated --format json
```

## Update Commands

```bash
# Update specific package
cargo update -p <package>

# Update all dependencies
cargo update

# Edit Cargo.toml for major version changes
# Then run cargo update
```

## Test Commands

```bash
cargo test
cargo check      # Fast type checking
cargo clippy     # Linting
cargo build      # Full build
```

## Common Ecosystem Groups

### Async Runtime
```
tokio
tokio-util
tokio-stream
```
Update together for compatibility.

### Serde
```
serde
serde_json
serde_yaml
```

### Web (Axum)
```
axum
axum-extra
tower
tower-http
```

### Web (Actix)
```
actix-web
actix-rt
actix-files
```

## Lockfile Handling

```bash
git add Cargo.toml Cargo.lock
```

## Version Constraints

Cargo.toml uses semantic versioning:
- `"1.0"` - Equivalent to `^1.0` (any compatible version)
- `"=1.0.5"` - Exact version
- `">=1.0, <2.0"` - Range

## Workspace Handling

For workspaces with multiple crates:
```bash
# Update across workspace
cargo update

# Update specific package in workspace
cargo update -p <package>
```

## Feature Flags

When updating, verify feature flags still work:
```bash
cargo build --all-features
cargo test --all-features
```
