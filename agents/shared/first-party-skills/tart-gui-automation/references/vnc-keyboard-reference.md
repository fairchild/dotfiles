# VNC Keyboard & Mouse Reference

## Coordinate System

Default Tart framebuffer: **2048x1536** (Retina 2x of 1024x768).

Change with: `tart set <vm> --display 1024x768` (non-Retina) or `tart set <vm> --display 2048x1536` (Retina).

The harness records actual dimensions in `session.json` as `framebuffer_width`/`framebuffer_height` after start.

## Keysym Names (vncdotool)

vncdotool uses X11 keysym names. Common mappings for macOS automation:

### Modifiers

| macOS Key | vncdotool keysym |
|-----------|-----------------|
| Command (Cmd) | `meta` or `meta_l` |
| Option (Alt) | `alt` or `alt_l` |
| Control | `ctrl` or `ctrl_l` |
| Shift | `shift` or `shift_l` |
| Right Command | `meta_r` |
| Right Option | `alt_r` |

**Important**: Use `meta`, not `super_l` or `command`. This is the most common mistake.

### Navigation

| Key | vncdotool keysym |
|-----|-----------------|
| Return/Enter | `return` or `enter` |
| Tab | `tab` |
| Escape | `esc` |
| Space | `space` or `spacebar` |
| Backspace | `bsp` |
| Delete (forward) | `del` or `delete` |
| Arrow Up | `up` |
| Arrow Down | `down` |
| Arrow Left | `left` |
| Arrow Right | `right` |
| Home | `home` |
| End | `end` |
| Page Up | `pgup` |
| Page Down | `pgdn` |
| Insert | `ins` |
| Caps Lock | `caplk` |
| Num Lock | `numlk` |
| Scroll Lock | `scrlk` |
| Pause | `pause` |
| Backslash | `bslash` |
| Forward Slash | `fslash` or `slash` |

### Function Keys

`f1` through `f20`

### Common macOS Shortcuts

| Action | Harness command |
|--------|----------------|
| Spotlight | `send-keys --keys "meta+space"` |
| Quit app | `send-keys --keys "meta+q"` |
| New window | `send-keys --keys "meta+n"` |
| Close window | `send-keys --keys "meta+w"` |
| Select all | `send-keys --keys "meta+a"` |
| Copy | `send-keys --keys "meta+c"` |
| Paste | `send-keys --keys "meta+v"` |
| Undo | `send-keys --keys "meta+z"` |
| Tab switch | `send-keys --keys "ctrl+tab"` |
| Force Quit | `send-keys --keys "meta+alt+escape"` |

## Mouse Operations

vncdotool operates on the full framebuffer coordinate space:

```python
client.mouseMove(x, y)   # Move cursor
client.mousePress(1)     # Left click (1=left, 2=middle, 3=right)
client.mouseDown(1)      # Hold left button
client.mouseUp(1)        # Release left button
client.mousePress(4)     # Scroll up
client.mousePress(5)     # Scroll down
```

### Mouse Button Map

| Button | vncdotool | Harness `--button` |
|--------|-----------|-------------------|
| Left click | `mousePress(1)` | `--button left` (default) |
| Middle click | `mousePress(2)` | `--button middle` |
| Right click | `mousePress(3)` | `--button right` |
| Scroll up | `mousePress(4)` | `scroll --direction up` |
| Scroll down | `mousePress(5)` | `scroll --direction down` |

### Harness Mouse Commands

```bash
# Click (by coordinates or landmark)
tart_vm_harness.py click \
  --session-file session.json --x 500 --y 300
tart_vm_harness.py click \
  --session-file session.json --landmark toolbar_open_menu

# Double-click
tart_vm_harness.py double-click \
  --session-file session.json --x 500 --y 300

# Right-click
tart_vm_harness.py click \
  --session-file session.json --x 500 --y 300 --button right

# Scroll
tart_vm_harness.py scroll \
  --session-file session.json --x 500 --y 300 --direction down --clicks 3

# Drag
tart_vm_harness.py drag \
  --session-file session.json --from-x 100 --from-y 200 --to-x 400 --to-y 500
```

### Double-Click Pattern (vncdotool)

vncdotool has no native double-click. The harness implements it as two rapid clicks:

```python
client.mouseMove(x, y)
client.mousePress(1)
time.sleep(0.05)
client.mousePress(1)
```

### Drag Pattern (vncdotool)

```python
client.mouseMove(from_x, from_y)
client.mouseDown(1)
client.mouseMove(to_x, to_y)
client.mouseUp(1)
```

## VNC Connection Lifecycle

- **Keep connections short**: connect, act, disconnect. Long-lived connections time out.
- **Reconnect on timeout**: if capture or input fails, the harness retries with fresh connections.
- **Exponential backoff**: capture retries use 0.4s, 0.8s, 1.6s, 3.2s delays.
- **Connection timeout**: 12 seconds per connect attempt.

## captureScreen Tips

- First capture after VM start may be slow (framebuffer initialization).
- The harness `capture` command handles retries automatically.
- Captured PNGs match the framebuffer resolution (e.g., 2048x1536 at Retina 2x).
- To verify coordinates, capture a frame and inspect pixel positions in an image editor.
