# Troubleshooting

## VM Won't Start

**Symptoms**: `tart run` exits immediately, error about disk or missing VM.

**Checks**:
1. `tart list` — verify the base VM exists
2. `df -h` — check disk space (VMs are ~50-80 GB)
3. Check `tart-run.log` in the output directory for errors
4. Ensure no other VM with the same name is running: `tart list | grep running`

## tart exec Fails

**Symptoms**: `tart exec` returns error or times out.

**Checks**:
1. Guest agent must be installed and running (included in `*-base` and `*-xcode` images)
2. VM must be fully booted (wait for VNC URL to appear before trying)
3. Try: `tart exec <vm> -- echo ok`
4. Vanilla images don't include the guest agent — use `*-base` or higher

## SSH Discovery Fails

**Symptoms**: `discover-ssh` scans all IPs but finds no match.

**Checks**:
1. Is Remote Login enabled in guest? Check via `tart exec <vm> -- systemsetup -getremotelogin`
2. Enable it: `tart_vm_harness.py enable-ssh --session-file session.json`
3. Is the VM on the expected bridge interface? Check `--bridge-interface` matches your network
4. Are credentials correct? Default: `admin` / `admin`
5. Is the shared folder mounted? In guest: `ls "/Volumes/My Shared Files/"`

## VNC Capture Fails

**Symptoms**: `capture` command errors after retries.

**Checks**:
1. Is the VM still running? `tart_vm_harness.py status --session-file session.json`
2. Is the VNC port reachable? `nc -z 127.0.0.1 <port>`
3. VNC password from session.json may have changed (rare — restart VM)
4. Try increasing timeout: the harness uses 12s connect + exponential backoff

## Keyboard Input Ignored

**Symptoms**: `send-keys` or `type-string` completes without error but nothing happens in guest.

**Checks**:
1. **Wrong keysym names**: Use `meta` not `super_l` or `command`. See `references/vnc-keyboard-reference.md`
2. **App not frontmost**: Click on the target window first, then send keys
3. **Focus lost**: macOS may show a dialog or notification stealing focus — capture and inspect
4. **Modifier stuck**: Disconnect/reconnect VNC to reset key state

## Clicks Miss Targets

**Symptoms**: Click at (x, y) doesn't hit the expected UI element.

**Checks**:
1. **Coordinate space mismatch**: Default framebuffer is 2048x1536 (Retina 2x). Check `framebuffer_width`/`framebuffer_height` in session.json
2. **Display changed**: `tart set <vm> --display` affects coordinates. Re-capture and measure
3. **Capture-and-inspect**: Take a screenshot, open in image editor, measure pixel coordinates of target element
4. **Dynamic layout**: If the window moved or resized, coordinates shift — capture immediately before clicking

## App Won't Activate / Launch

**Symptoms**: App process starts but window doesn't appear, or `open -a` has no visible effect.

**Checks**:
1. **Sequoia+ restrictions**: Some operations need Accessibility permissions pre-granted
2. Use `open -a <app>` or `open <path-to-binary>` instead of running the binary directly
3. Click on the app's Dock icon or menu bar via VNC to bring it forward
4. Check if a permission dialog is blocking: capture a frame and inspect

## Permission Dialogs

**Symptoms**: Unexpected dialogs appear asking for permissions.

**Checks**:
1. Pre-grant permissions in the base image before snapshotting
2. If dialog appears at runtime, dismiss via VNC click at the button coordinates
3. Common dialogs: Accessibility, Screen Recording, Full Disk Access
4. For `cliclick`: grant Accessibility in System Settings > Privacy & Security

## No Workspace in DB

**Symptoms**: App launches but toolbar button is disabled or missing because no workspace is selected.

**Checks**:
1. The app may need a workspace created before the toolbar button activates
2. Create a workspace via the app's UI (New Workspace) or seed the SwiftData store
3. Alternatively, interact with the app via AppleScript or accessibility scripting

## Source Repos for Deep Debugging

- [cirruslabs/tart](https://github.com/cirruslabs/tart) — VM runtime, `tart exec` implementation
- [cirruslabs/tart-guest-agent](https://github.com/cirruslabs/tart-guest-agent) — Agent that enables `tart exec`
- [cirruslabs/packer-plugin-tart](https://github.com/cirruslabs/packer-plugin-tart) — Image building
- [cirruslabs/macos-image-templates](https://github.com/cirruslabs/macos-image-templates) — What's in each image tier
