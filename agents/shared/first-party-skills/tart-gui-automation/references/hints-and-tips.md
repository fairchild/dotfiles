# Hints, Tips & Gotchas

Precise, non-obvious findings from real automation sessions.

> **Machine-readable coordinates**: For projects using this skill, calibrated
> coordinates should live in `.tart/target.yaml` (see `references/target-manifest.md`).
> The tables below are reference/context for understanding the coordinate space.
> Use `--landmark` or batch landmark steps to avoid hard-coding pixel values.

> **Batch operations**: Many of the VNC connection lifecycle issues below are
> mitigated by the `batch` command, which executes multiple operations in a
> single VNC connection. Prefer `batch` for multi-step flows.

---

## VNC Coordinate Calibration (macOS Tahoe, 2048×1536)

The physical y values for UI rows are **higher than the logical point math suggests** because the unified title+toolbar row sits below the menu bar with padding.

| UI Zone | Physical y (approx) |
|---------|---------------------|
| macOS system menu bar | 0–45 |
| Window toolbar / title bar row | **95–135** |
| Dock | ~1490 |

**Do not assume y = logical_pt × 2.** The menu bar is ~22pt (44px) and the toolbar adds another ~28pt (56px) with padding — putting the toolbar hit zone at y≈125, not y≈82. Always calibrate with a sweep.

### Calibration recipe

Sweep y from 70 to 140 at a known-good x (e.g., where a labeled button exists) using `mouseDown` + 1s hold + capture at each step. The step where a button triggers (dialog, menu, or visual change) tells you the exact row.

```python
for y in range(70, 141, 5):
    client.mouseMove(known_x, y)
    client.mouseDown(1)
    time.sleep(1.0)
    client.captureScreen(f"cal_y{y:03d}.png")
    client.mouseUp(1)
    client.keyDown("esc"); client.keyUp("esc")
    time.sleep(0.4)
```

### WorkspaceManager toolbar (confirmed 2026-03-01)

| Element | x | y |
|---------|---|---|
| "Zed" left button of ControlGroup | ~1790 | 125 |
| "Open ▾" Menu button of ControlGroup | ~1870 | 125 |
| WorkspaceManager Dock icon | 1650 | 1490 |

---

## VNC Connection Lifecycle (extends `vnc-keyboard-reference.md`)

### `client.disconnect()` hangs — use `os._exit(0)`

vncdotool uses a Twisted reactor. `client.disconnect()` frequently blocks indefinitely on long-lived connections. Always terminate with:

```python
import os
# at end of main():
os._exit(0)
```

This skips `atexit` handlers and Twisted teardown. The OS closes the TCP socket cleanly.

### Never wrap VNC scripts with `timeout`

```bash
# BAD — process kill leaves TCP in CLOSE_WAIT for ~40s
timeout 240 vnc_script.py

# GOOD — script manages its own lifecycle with os._exit(0)
vnc_script.py
```

A CLOSE_WAIT socket blocks new VNC connections. Wait ~40s before reconnecting or you'll get `Connection refused`.

### Testing VNC availability without breaking it

```bash
# CORRECT — receive-only, doesn't interrupt RFB handshake
nc 127.0.0.1 49830 < /dev/null

# WRONG — sends a newline, corrupts RFB negotiation
echo "" | nc 127.0.0.1 49830
```

The VNC server responds with `RFB 003.008\n` on connect. Any inbound data before the server message breaks the handshake.

### Single `api.connect()` per process

vncdotool's Twisted reactor cannot be restarted. If you call `api.connect()` twice in one process (e.g., in a loop), the second call fails with `ReactorNotRestartable`. Use one connection per script, or spawn a subprocess for each session.

---

## Screen Sharing.app Blocks VNC

Tart with `--vnc-experimental` auto-opens `Screen Sharing.app` on the host to display the VM. While open, it holds the VNC server connection, blocking vncdotool.

```bash
# Check if it's holding the slot
lsof -i :<vnc_port> | grep "Screen"

# Kill it to free the slot (VM GUI closes on host, VM keeps running)
pkill -f "Screen Sharing"
```

After killing Screen Sharing, wait ~3s before connecting with vncdotool.

---

## vncdotool API — Missing Methods

`client.type(text)` **does not exist**. Calling it raises `AttributeError: type object 'VNCDoToolClient' has no attribute 'type'`.

To type text, either:

```python
# Option A: single characters with keyPress
for ch in "hello":
    client.keyPress(ch)

# Option B: paste via clipboard (set via tart exec, paste via VNC)
# Host: printf "hello" | tart exec <vm> pbcopy
# VNC:  client.keyDown("meta"); client.keyPress("v"); client.keyUp("meta")
```

---

## SwiftUI Menu vs Button — Click Behavior

A SwiftUI `Menu` in a toolbar ControlGroup responds to **full click** (`mousePress` = mouseDown + mouseUp), not just `mouseDown` alone.

- `mouseDown` + hold → does NOT reliably open a SwiftUI Menu dropdown
- `mousePress(1)` (click) → opens the dropdown immediately

Contrast with Dock icons and macOS menu bar items (File, Edit…), which also respond to `mousePress`.

---

## macOS App Activation on Tahoe

`NSRunningApplication.activate(options: .activateIgnoringOtherApps)` is **deprecated in macOS 14+** and has **no effect on Tahoe**. Running this via `tart exec swift` does nothing.

Reliable activation methods:
1. **Click Dock icon** at VNC coordinates — always works
2. **Cmd+Tab** app switcher — works but requires cycling to the right app
3. **`open -b <bundle-id>`** via `tart exec` — works if bundle is registered with Launch Services

---

## `tart exec` Syntax — No `--` Separator

```bash
# CORRECT
tart exec my-vm echo hello
tart exec my-vm /usr/bin/swift /Volumes/My\ Shared\ Files/share/script.swift

# WRONG — the -- causes a parse error
tart exec my-vm -- echo hello
```

---

## Accessibility Dialog Blocks System Events

When `tart-guest-agent` injects VNC events, macOS shows:
> "tart-guest-agent would like to control this computer"

While this dialog is visible, `System Events` AppleScript calls time out with error **-1712** (`AppleEvent timed out`). The dialog must be dismissed (or pre-granted in the base image) before osascript automation works.

Pre-granting in the base image:
```bash
# On guest (via tart exec or SSH), add tart-guest-agent to TCC.db
# Or use a Packer provisioner that runs this before snapshotting
```

---

## Estimating Physical Coordinates from Screenshots

VNC captures are saved at full physical resolution (see `vnc-keyboard-reference.md` for defaults). Viewers/editors typically display them scaled. To convert visual estimates to physical coords:

```
physical_x = display_x / display_width  × framebuffer_width
# e.g., display_x=448 in a 512px-wide render of a 2048px framebuffer:
# physical_x = (448 / 512) × 2048 = 1792
```

Simpler rule for 2048-wide default: **multiply display pixel position by 4** when the rendered image appears 512px wide.

---

## Dock Icon Position Discovery

The Dock icon row is at y≈1490 (physical) on a 2048×1536 framebuffer. Icon x positions vary by Dock contents. To find an icon:

1. Capture `sw_dock.png`
2. Visually locate the icon at display coords (x_d, y_d)
3. Scale: `x_physical = x_d × 4`, `y_physical = y_d × 4`
4. Verify with a click that produces the expected result (app activates)

If clicking x=1650 opens the wrong app, try ±50px increments. Apps shift position when Dock contents change.

---

## macOS Menu Bar Positions (approximate, 2048-wide)

The menu bar row is at **y≈46** physical.

| Menu item | Physical x |
|-----------|-----------|
| Apple logo | ~14 |
| App name (e.g., "WorkspaceManager") | ~80–145 |
| File | ~155–185 |
| Edit | ~195–220 |

Clicking the **app name** opens the app menu (About, Settings, Quit…), not "File". To click "File", target x≈165, not x=143.
