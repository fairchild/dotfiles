# Tart GUI Automation Setup Reference

## 1) Host prerequisites

1. Install Tart on host:
   - `brew install cirruslabs/cli/tart`
2. Install media + automation helpers:
   - `brew install ffmpeg`
   - `brew install uv`
3. Verify networking interface for bridged mode:
   - `tart run --help` and use `--net-bridged=<interface>` (usually `en0`)

## 2) Base VM preparation

Choose the right image for your use case:

| Use case | Recommended image | Pull command |
|----------|------------------|--------------|
| Screenshot-only automation | `macos-tahoe-base` | `tart pull ghcr.io/cirruslabs/macos-tahoe-base:latest` |
| Build/test Swift apps | `macos-tahoe-xcode` | `tart pull ghcr.io/cirruslabs/macos-tahoe-xcode:latest` |
| Minimal/custom | `macos-tahoe-vanilla` | `tart pull ghcr.io/cirruslabs/macos-tahoe-vanilla:latest` |

See `references/image-matrix.md` for the full image matrix with Sequoia variants.

**Display resolution** (optional):
```bash
tart set <vm> --display 1024x768    # Non-Retina, smaller framebuffer
tart set <vm> --display 2048x1536   # Retina 2x (default)
```

## 3) Guest command execution

**Primary method: `tart exec`** — works out of the box with `*-base` and `*-xcode` images (guest agent pre-installed):
```bash
scripts/tart_vm_harness.py exec \
  --session-file session.json -- <command>
```

**Fallback: SSH** — for when tart exec is unavailable (vanilla images, custom setups):
1. Enable Remote Login if not already on:
   ```bash
   scripts/tart_vm_harness.py enable-ssh --session-file session.json
   ```
2. Discover SSH host:
   ```bash
   scripts/tart_vm_harness.py discover-ssh --session-file session.json
   ```

**Note**: SSH is NOT always available. Vanilla images have Remote Login disabled. The `discover-ssh` command will warn if Remote Login is off (when tart exec is available to check).

## 4) Guest configuration (optional)

For VNC-based mouse automation, install `cliclick` in the guest:
```bash
scripts/tart_vm_harness.py exec \
  --session-file session.json -- brew install cliclick
```

Grant Accessibility permission for `cliclick` via System Settings > Privacy & Security (or pre-grant in a custom base image).

Keep guest credentials stable for automation: default `admin`/`admin` in all Cirrus Labs images.

## 5) Shared-folder and target setup

1. Run Tart with a shared directory (the harness `start` command does this):
   - `--dir <share-name>:<host-path>`
2. Confirm guest mount path:
   - `/Volumes/My Shared Files/<share-name>`
3. Update target automation commands for your app:
   - launch command
   - click coordinates or semantic selectors
   - expected completion signal (log line, DOM marker, visible text)

## 6) Headless-first execution policy

1. Default to headless runs:
   - do not open VNC viewer unless explicitly requested.
2. Use VNC only for live debugging / manual observation.
3. Capture evidence with frame grabs and encoded MP4 instead of keeping an
   interactive viewer open.

## 7) Cleanup order (important)

When VNC was opened, use this order:

1. Close VNC client session first (for macOS built-in viewer: quit Screen Sharing).
2. Stop VM (`tart stop <run-vm>`).
3. Delete ephemeral VM clone (`tart delete <run-vm>`) unless intentionally kept.

This prevents stale viewer sessions and reduces host resource leakage.

## 8) Reliability checklist

- Recreate ephemeral run VM from a known base for each run.
- Write a run-scoped `session.json` with VM name, VNC URL, log path, and SSH host.
- Retry VNC captures (`3-5` attempts with exponential backoff).
- Use deterministic waits tied to observable state (logs/UI markers), not long fixed sleeps.
- Keep one active GUI workload per VM.
- Check VM health with the `status` command before running complex workflows.
