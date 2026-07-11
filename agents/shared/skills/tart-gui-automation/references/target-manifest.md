# Target Manifest Schema

Target manifests encode project-specific GUI automation knowledge: calibrated coordinates, app identity, timing hints, and flow recipes. They live in the **project repo** (not the skill), keeping the skill generic.

## File Locations

```
<project-root>/
  .tart/
    target.yaml          # primary target manifest
    flows/               # named flow recipes
      activate-app.yaml
      verify-dropdown.yaml
```

## target.yaml Schema

```yaml
target:
  app_name: <string>           # display name of the app under test
  bundle_id: <string>          # macOS bundle identifier
  base_vm: <string>            # Tart base image name
  display: "<W>x<H>"          # framebuffer dimensions these coords are calibrated for
  launch_cmd: <string>         # optional: command to launch the app in guest

landmarks:
  <name>: { x: <int>, y: <int> }
  # Physical pixel coordinates in the framebuffer coordinate space.
  # Names should be snake_case, prefixed by zone: toolbar_, menu_, dock_, sidebar_

timing:
  post_click_ms: <int>        # default wait after a click
  app_launch_ms: <int>        # wait after launching the app
  menu_settle_ms: <int>       # wait after a menu opens
  dismiss_delay_ms: <int>     # wait after dismissing a dialog/menu

calibrated:
  date: "<YYYY-MM-DD>"        # when coordinates were last confirmed
  display: "<W>x<H>"          # display setting during calibration
  os: <string>                # macOS version
  notes: <string>             # free-form calibration notes
```

### Landmark Naming Conventions

| Prefix | Zone | Examples |
|--------|------|----------|
| `toolbar_` | App toolbar buttons | `toolbar_open_menu`, `toolbar_zed` |
| `menu_` | Menu bar items | `menu_file`, `menu_edit`, `menu_app_name` |
| `dock_` | Dock icons | `dock_icon` |
| `sidebar_` | Sidebar elements | `sidebar_first_repo`, `sidebar_first_ws` |
| `dialog_` | Dialog buttons | `dialog_ok`, `dialog_cancel` |
| `apple_` | System UI | `apple_menu` |

### Coordinates

All coordinates are **physical pixels** in the VNC framebuffer space. For a default Tart VM at 2048x1536 (Retina 2x), the coordinate space is 2048 wide and 1536 tall. Do not use logical/point coordinates — store what you measure.

Record the `display` value so future sessions know which resolution the coordinates apply to. If the display setting changes, recalibrate.

## Using Landmarks from the Harness

```bash
# Click by landmark name (resolves from .tart/target.yaml)
tart_vm_harness.py click \
  --session-file session.json \
  --landmark toolbar_open_menu

# Click by raw coordinates (unchanged)
tart_vm_harness.py click \
  --session-file session.json \
  --x 1870 --y 125

# Batch with landmarks
tart_vm_harness.py batch \
  --session-file session.json \
  --steps-json '{"steps": [{"action": "click", "landmark": "dock_icon"}, {"action": "wait", "seconds": 2}]}'
```

The `--target` flag defaults to `.tart/target.yaml`. Override with `--target path/to/other.yaml`.

## Flow Recipe Schema

Flow files are **agent-readable recipes**, not harness-executable scripts. The agent reads the steps, resolves landmark names from `target.yaml`, and issues harness commands. Note: flow YAML uses `send_keys` (underscore) while the batch JSON command uses `send-keys` (hyphen) — the agent translates between formats.

```yaml
name: <string>                 # flow identifier
description: <string>          # what this flow does

preconditions:                 # optional: what must be true before running
  - <key>: <value>

steps:
  - action: click|capture|send_keys|type|wait
    landmark: <name>           # resolves from target.yaml (for click)
    output: <path>             # for capture
    keys: <combo>              # for send_keys
    text: <string>             # for type
    seconds: <float>           # for wait
    wait_ms: <int>             # pause after this step
    note: <string>             # explains intent (for agent and humans)

verify: <string>               # natural-language description of success criteria
```

### Flow Design Principles

1. Steps reference landmark **names**, not coordinates.
2. `wait_ms` overrides the default timing from `target.yaml`.
3. `note` explains intent — helps the agent reason about failures.
4. `verify` describes what success looks like in natural language.
5. No conditionals or loops. The agent handles branching and error recovery.

## Calibration Workflow

When coordinates change (UI update, window resize, different display):

1. Run a coordinate sweep (see `references/hints-and-tips.md` calibration recipe).
2. Update `.tart/target.yaml` with new values.
3. Update `calibrated.date` and `calibrated.notes`.
4. Commit the change with the app code.

The `calibrated.date` field signals freshness. An agent can compare this against recent app changes to decide if recalibration is needed.
