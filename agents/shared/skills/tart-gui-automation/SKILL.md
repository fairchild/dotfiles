---
name: tart-gui-automation
description: Run deterministic GUI workflows in isolated Tart macOS VMs. Provides VM lifecycle management, guest command execution via tart exec (SSH fallback), VNC interaction (clicks, keyboard, captures), batch operations, target manifests for project-specific landmarks, and clean teardown. Headless by default with optional VNC observation.
license: Apache 2.0
disable-model-invocation: true
---

# Tart GUI Automation

## Quick Start

```bash
# 1. Start VM
scripts/tart_vm_harness.py start \
  --base-vm macos-tahoe-xcode \
  --share-name workspaces --share-path .

# 2. Run commands in guest
scripts/tart_vm_harness.py exec \
  --session-file output/tart-harness/*/session.json -- swift build

# 3. Capture screenshot (optionally resize for LLM consumption)
scripts/tart_vm_harness.py capture \
  --session-file output/tart-harness/*/session.json \
  --output output/screenshot.png --max-dimension 1280

# 4. Click by landmark name (from .tart/target.yaml)
scripts/tart_vm_harness.py click \
  --session-file output/tart-harness/*/session.json \
  --landmark toolbar_open_menu

# 5. Multi-step batch (single VNC connection)
scripts/tart_vm_harness.py batch \
  --session-file output/tart-harness/*/session.json \
  --steps-json '{"steps": [
    {"action": "click", "landmark": "dock_icon"},
    {"action": "wait", "seconds": 2},
    {"action": "click", "landmark": "toolbar_open_menu"},
    {"action": "capture", "output": "dropdown.png"}
  ]}'

# 6. Teardown
scripts/tart_vm_harness.py teardown \
  --session-file output/tart-harness/*/session.json
```

## Image Selection

| Need | Image | Size |
|------|-------|------|
| Screenshot/VNC only | `*-base` (e.g., `macos-tahoe-base`) | ~20 GB |
| Build Swift apps | `*-xcode` (e.g., `macos-tahoe-xcode`) | ~67 GB |
| Minimal footprint | `*-vanilla` + custom setup | ~15 GB |

See `references/image-matrix.md` for the full matrix.

## Guest Command Execution

**Primary: `tart exec`** — runs commands via the guest agent (no SSH needed):
```bash
scripts/tart_vm_harness.py exec \
  --session-file session.json -- echo hello
```

**Fallback: SSH** — used automatically if `tart exec` fails and `ssh_host` is in session:
```bash
# First enable SSH if needed
scripts/tart_vm_harness.py enable-ssh --session-file session.json

# Then discover the SSH host
scripts/tart_vm_harness.py discover-ssh --session-file session.json
```

The `start` command probes `tart exec` and records `tart_exec_available` in session.json.

## Commands

### Lifecycle

| Command | Purpose |
|---------|---------|
| `start` | Clone base VM, start with VNC + shared folder, probe tart exec |
| `teardown` | Close VNC, stop VM, delete clone |
| `status` | Health check: VM, process, tart exec, VNC, SSH |

### Guest Execution

| Command | Purpose |
|---------|---------|
| `exec` | Run command via tart exec (SSH fallback) |
| `enable-ssh` | Enable Remote Login via tart exec |
| `discover-ssh` | Find guest SSH host on bridge subnet |

### VNC Interaction

| Command | Purpose |
|---------|---------|
| `capture` | Capture one VNC frame as PNG (`--max-dimension` for resize) |
| `click` | Mouse click at (x,y) or `--landmark` name. `--button left\|right\|middle` |
| `double-click` | Double-click at (x,y) or `--landmark` name |
| `scroll` | Scroll up/down at position (`--direction`, `--clicks`) |
| `drag` | Drag from one point to another (`--from-x/y`, `--to-x/y`) |
| `type-string` | Type text character by character |
| `send-keys` | Key combination (e.g., `meta+space`) |
| `batch` | Multiple VNC operations in a **single connection** |

## Batch Operations

The `batch` command executes a sequence of VNC steps in one connection, avoiding the one-connection-per-process overhead. Steps are provided as JSON:

```json
{"steps": [
  {"action": "click", "x": 1870, "y": 125},
  {"action": "click", "landmark": "toolbar_open_menu"},
  {"action": "double-click", "x": 500, "y": 300},
  {"action": "type", "text": "hello world"},
  {"action": "send-keys", "keys": "meta+s"},
  {"action": "scroll", "x": 500, "y": 300, "direction": "down", "clicks": 3},
  {"action": "drag", "from_x": 100, "from_y": 200, "to_x": 400, "to_y": 500},
  {"action": "capture", "output": "step.png", "max_dimension": 1280},
  {"action": "wait", "seconds": 1.5}
]}
```

Pass via `--steps-file path.json` or `--steps-json '{...}'`.

## Target Manifests

Projects can store calibrated UI coordinates in `.tart/target.yaml`:

```yaml
landmarks:
  toolbar_open_menu: { x: 1870, y: 125 }
  dock_icon:         { x: 1650, y: 1490 }
```

The harness resolves landmark names via `--landmark` (on `click`, `double-click`) and in batch steps. See `references/target-manifest.md` for the full schema.

Flow recipes in `.tart/flows/` provide agent-readable step sequences for common workflows. The agent reads the YAML, resolves landmarks, and issues harness commands.

## Coordinate Scaling

For resolution-independent coordinates, use `--logical-resolution` at start:

```bash
scripts/tart_vm_harness.py start \
  --base-vm macos-tahoe-xcode \
  --logical-resolution 1024x768
```

All subsequent commands interpret coordinates as logical and scale to the physical framebuffer automatically. Omit for raw physical coordinates (default).

## VNC Keyboard Quick Reference

- **Command key**: `meta` (not `super_l` or `command`)
- **Default framebuffer**: 2048x1536 (Retina 2x)
- **Common shortcuts**: `meta+space` (Spotlight), `meta+q` (Quit), `meta+w` (Close)

See `references/vnc-keyboard-reference.md` for the full keysym table.

## Workflow

1. **Start** an ephemeral VM (headless by default, `--open-vnc` for debugging).
2. **Execute** build/launch commands via `exec` (tart exec primary, SSH fallback).
3. **Interact** via VNC: `click`, `batch`, `type-string`, `send-keys`, `scroll`, `drag`.
4. **Capture** frames for verification evidence (`--max-dimension` for LLM-sized images).
5. **Teardown** in safe order: close VNC client, stop VM, delete clone.

## Troubleshooting Quick Fixes

| Problem | Fix |
|---------|-----|
| `tart exec` fails | Check guest agent installed (`*-base` or higher) |
| SSH discovery fails | Run `enable-ssh` first, check bridge interface |
| Wrong keysym name | Use `meta` not `super_l`. See VNC reference |
| Click misses target | Check 2048x1536 coordinate space. Capture and measure |
| App won't activate | Use `open -a`, click via VNC, check permission dialogs |
| Multi-step VNC fails | Use `batch` instead of individual commands |

See `references/troubleshooting.md` for the full debugging guide.

## Reference Docs

- `references/setup-and-target.md` — Host prerequisites, guest configuration
- `references/vnc-keyboard-reference.md` — Keysym names, coordinates, shortcuts
- `references/image-matrix.md` — Image tiers, sizes, pull commands
- `references/troubleshooting.md` — Common failures and fixes
- `references/hints-and-tips.md` — Precise calibration data, gotchas, non-obvious behaviors
- `references/target-manifest.md` — Target manifest and flow recipe schema

## Source References

- [cirruslabs/tart](https://github.com/cirruslabs/tart) — VM runtime
- [cirruslabs/tart-guest-agent](https://github.com/cirruslabs/tart-guest-agent) — Enables `tart exec`
- [cirruslabs/macos-image-templates](https://github.com/cirruslabs/macos-image-templates) — Image Packer templates
- [cirruslabs/packer-plugin-tart](https://github.com/cirruslabs/packer-plugin-tart) — Packer plugin

## Guardrails

- Default to headless runs (`--no-open-vnc`).
- Use `--open-vnc` only for debugging or live walkthroughs.
- Always teardown ephemeral VMs after run unless explicitly preserving them.
- If VNC was opened, close VNC client before VM shutdown.
- Prefer one run VM per flow to avoid cross-run state leakage.
