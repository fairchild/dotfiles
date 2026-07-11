# Cirrus Labs Tart Image Matrix

## Image Layering

Cirrus Labs provides macOS images in 4 tiers, each building on the previous:

```
vanilla → base → xcode → runner
```

## Image Tiers

| Tier | What it adds | Use case |
|------|-------------|----------|
| **vanilla** | Clean macOS install, no tools | Base for custom images |
| **base** | Guest agent, Homebrew, SSH enabled | Screenshot-only automation, simple scripts |
| **xcode** | Xcode + CLT, Swift toolchain, `simctl` | Building/testing Swift/iOS apps |
| **runner** | CI runner config, GitHub Actions agent | CI/CD pipelines |

## Available Images

### macOS Tahoe (26)

| Image | SSH | Homebrew | Xcode | Guest Agent | Compressed Size | Pull Command |
|-------|-----|----------|-------|-------------|----------------|--------------|
| `macos-tahoe-vanilla` | No | No | No | No | ~15 GB | `tart pull ghcr.io/cirruslabs/macos-tahoe-vanilla:latest` |
| `macos-tahoe-base` | Yes | Yes | No | Yes | ~20 GB | `tart pull ghcr.io/cirruslabs/macos-tahoe-base:latest` |
| `macos-tahoe-xcode` | Yes | Yes | Yes | Yes | ~67 GB | `tart pull ghcr.io/cirruslabs/macos-tahoe-xcode:latest` |

### macOS Sequoia (15)

| Image | SSH | Homebrew | Xcode | Guest Agent | Compressed Size | Pull Command |
|-------|-----|----------|-------|-------------|----------------|--------------|
| `macos-sequoia-vanilla` | No | No | No | No | ~15 GB | `tart pull ghcr.io/cirruslabs/macos-sequoia-vanilla:latest` |
| `macos-sequoia-base` | Yes | Yes | No | Yes | ~20 GB | `tart pull ghcr.io/cirruslabs/macos-sequoia-base:latest` |
| `macos-sequoia-xcode` | Yes | Yes | Yes | Yes | ~60 GB | `tart pull ghcr.io/cirruslabs/macos-sequoia-xcode:latest` |

## Image Selection Guide

| Need | Recommended Image |
|------|------------------|
| Screenshot capture only | `*-base` |
| Build Swift/SwiftUI app | `*-xcode` |
| Run Xcode tests / simctl | `*-xcode` |
| Custom CI runner | `*-runner` |
| Minimal footprint | `*-vanilla` + custom provisioning |

## Default Credentials

All Cirrus Labs images: **admin / admin**

## Custom Images

Create custom images via Packer:
- Plugin: [cirruslabs/packer-plugin-tart](https://github.com/cirruslabs/packer-plugin-tart)
- Templates: [cirruslabs/macos-image-templates](https://github.com/cirruslabs/macos-image-templates)

Or snapshot a running VM:
```bash
tart stop <vm>
tart clone <vm> my-custom-image
```

## Source Repositories

- [cirruslabs/tart](https://github.com/cirruslabs/tart) — VM runtime
- [cirruslabs/tart-guest-agent](https://github.com/cirruslabs/tart-guest-agent) — Guest agent for `tart exec`
- [cirruslabs/macos-image-templates](https://github.com/cirruslabs/macos-image-templates) — Packer templates
- [cirruslabs/packer-plugin-tart](https://github.com/cirruslabs/packer-plugin-tart) — Packer plugin
