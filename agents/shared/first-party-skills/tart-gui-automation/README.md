# tart-gui-automation

A Claude Code skill for scripting macOS GUI interactions inside ephemeral [Tart](https://github.com/cirruslabs/tart) VMs. Runs headless by default, captures screenshots as verification evidence, and tears down cleanly after each run.

## What it does

An AI agent (Claude Code, Codex, etc.) uses this skill to:

1. **Spin up** a disposable macOS VM cloned from a base image
2. **Build/run** software inside the guest via `tart exec` (or SSH)
3. **Drive the GUI** over VNC — click buttons, type text, send keyboard shortcuts, scroll, drag
4. **Capture screenshots** as proof that a workflow succeeded
5. **Tear down** the VM, leaving no state behind

The agent reads `SKILL.md` for the full command reference. This README is for humans.

## Prerequisites

- macOS host with Apple Silicon
- [Tart](https://github.com/cirruslabs/tart) installed (`brew install cirruslabs/cli/tart`)
- [uv](https://docs.astral.sh/uv/) installed (runs the harness script with pinned dependencies)
- A Tart base image pulled (e.g., `tart pull ghcr.io/cirruslabs/macos-tahoe-base:latest`)

No other setup needed. The harness script manages its own Python dependencies via PEP 723 inline metadata.

## How it works

```
┌─────────────────────────────────────────────────────┐
│  Host (your Mac)                                    │
│                                                     │
│  Claude Code ──reads──▶ SKILL.md (command reference)│
│       │                 .tart/target.yaml (landmarks)│
│       │                 .tart/flows/*.yaml (recipes) │
│       │                                             │
│       ▼                                             │
│  tart_vm_harness.py                                 │
│       │                                             │
│       ├─ tart clone/run  ──▶ Ephemeral VM           │
│       ├─ tart exec       ──▶ Guest commands         │
│       ├─ VNC (vncdotool) ──▶ GUI interaction        │
│       └─ tart stop/delete──▶ Clean teardown         │
│                                                     │
│  output/tart-harness/<timestamp>/                   │
│       ├─ session.json    (VM state, VNC endpoint)   │
│       └─ *.png           (screenshot evidence)      │
└─────────────────────────────────────────────────────┘
```

## Typical agent session

```bash
# Agent starts a VM, builds the app, clicks around, captures proof, tears down
scripts/tart_vm_harness.py start --base-vm macos-tahoe-xcode
scripts/tart_vm_harness.py exec  --session-file output/tart-harness/*/session.json -- swift build
scripts/tart_vm_harness.py exec  --session-file output/tart-harness/*/session.json -- open -a MyApp
scripts/tart_vm_harness.py batch  --session-file output/tart-harness/*/session.json \
  --steps-json '{"steps": [
    {"action": "click", "landmark": "toolbar_open_menu"},
    {"action": "wait", "seconds": 0.5},
    {"action": "capture", "output": "menu-open.png", "max_dimension": 1280}
  ]}'
scripts/tart_vm_harness.py teardown --session-file output/tart-harness/*/session.json
```

The agent gets all of this from `SKILL.md`. You don't need to prompt it with commands.

## Project-specific knowledge: target manifests

Each project can store calibrated UI coordinates in `.tart/target.yaml`:

```yaml
landmarks:
  toolbar_open_menu: { x: 1870, y: 125 }
  dock_icon:         { x: 1650, y: 1490 }
```

The agent uses `--landmark toolbar_open_menu` instead of raw coordinates. This means:
- Landmarks survive across sessions (no re-discovery sweeps)
- Coordinates are version-controlled with the app code
- Recalibration is a YAML edit, not a prompt change

Optional **flow recipes** in `.tart/flows/` give the agent step-by-step playbooks for common workflows (e.g., "activate app", "verify dropdown works").

See `references/target-manifest.md` for the full schema.

## File layout

```
skills/tart-gui-automation/
  SKILL.md                          # Agent-facing command reference (loaded into context)
  README.md                         # This file (human-facing)
  scripts/tart_vm_harness.py        # Single-file UV script — the entire harness
  references/
    setup-and-target.md             # Host prerequisites, guest configuration
    vnc-keyboard-reference.md       # VNC keysym names, mouse buttons, shortcuts
    image-matrix.md                 # Tart image tiers, sizes, pull commands
    target-manifest.md              # Target manifest and flow recipe schema
    hints-and-tips.md               # Calibration data, gotchas, non-obvious behaviors
    troubleshooting.md              # Common failures and fixes
  agents/
    openai.yaml                     # OpenAI agent configuration
```

The agent reads `SKILL.md` automatically. Reference docs are loaded on demand when the agent needs deeper context (keyboard mappings, troubleshooting, etc.).

## Key design decisions

- **Single script, no install**: `tart_vm_harness.py` is a self-contained UV script. Dependencies (vncdotool, Pillow, paramiko, pyyaml) are declared inline and resolved automatically.
- **Headless by default**: VMs run without opening a VNC viewer. Pass `--open-vnc` when you want to watch.
- **Batch operations**: Multi-step VNC interactions run in a single connection to avoid vncdotool's Twisted reactor restart limitation.
- **Ephemeral VMs**: Each run clones from a base image and deletes the clone on teardown. No cross-run state leakage.
- **Screenshot resize**: `--max-dimension 1280` on capture produces LLM-friendly image sizes.

## Adding this skill to a project

1. Ensure the skill is available to Claude Code (symlinked or installed at `~/.claude/skills/tart-gui-automation`)
2. Optionally create `.tart/target.yaml` in your project with calibrated landmarks
3. Optionally create `.tart/flows/` with workflow recipes
4. The agent will discover and use the skill automatically when asked to do GUI verification tasks
