#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "paramiko>=3.4.0",
#   "vncdotool>=1.2.0",
#   "Pillow>=11.0.0",
#   "pyyaml>=6.0",
# ]
# ///

"""Headless-first Tart VM harness for deterministic GUI automation."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
import paramiko
from PIL import Image
from vncdotool import api

# ---------------------------------------------------------------------------
# Logging / utilities
# ---------------------------------------------------------------------------


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def fail(message: str) -> RuntimeError:
    return RuntimeError(message)


def run_command(
    argv: list[str],
    *,
    check: bool = True,
    capture_output: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=check,
        text=True,
        capture_output=capture_output,
        cwd=str(cwd) if cwd else None,
    )


def require_command(name: str) -> None:
    result = run_command(["bash", "-lc", f"command -v {shlex.quote(name)}"], check=False)
    if result.returncode != 0:
        raise fail(f"missing required command: {name}")


def load_session(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise fail(f"session file does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_session(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def parse_vnc_url(log_text: str) -> str:
    match = re.search(r"Opening\s+(vnc://\S+)", log_text)
    if not match:
        return ""
    return match.group(1).rstrip(".")


def wait_for_vnc_url(log_path: Path, process: subprocess.Popen[str], timeout_seconds: int) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if process.poll() is not None:
            text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
            raise fail(f"tart run exited before VNC endpoint was available\n{text}")

        if log_path.exists():
            text = log_path.read_text(encoding="utf-8", errors="replace")
            url = parse_vnc_url(text)
            if url:
                return url

        time.sleep(0.4)

    raise fail(f"timed out waiting for VNC URL in {log_path}")


def ensure_vm_exists(name: str) -> None:
    result = run_command(["tart", "get", name], check=False)
    if result.returncode != 0:
        raise fail(f"VM not found: {name}")


def vm_exists(name: str) -> bool:
    result = run_command(["tart", "get", name], check=False)
    return result.returncode == 0


def close_screen_sharing() -> None:
    applescript = 'tell application "Screen Sharing" to quit'
    run_command(["osascript", "-e", applescript], check=False)


def scale_coords(session: dict[str, Any], x: int, y: int) -> tuple[int, int]:
    sf = session.get("scale_factor", 1.0)
    return (int(x * sf), int(y * sf))


def resolve_landmark(target_path: Path, name: str) -> tuple[int, int]:
    target = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    landmarks = target.get("landmarks", {})
    if name not in landmarks:
        raise fail(f"landmark {name!r} not found in {target_path}")
    lm = landmarks[name]
    x, y = lm.get("x"), lm.get("y")
    if x is None or y is None:
        raise fail(f"landmark {name!r} missing x or y in {target_path}")
    return (int(x), int(y))


def resolve_click_coords(
    args: argparse.Namespace, session: dict[str, Any]
) -> tuple[int, int]:
    """Resolve (x, y) from either --landmark or --x/--y, applying coordinate scaling."""
    if getattr(args, "landmark", None):
        target_path = Path(getattr(args, "target", ".tart/target.yaml"))
        x, y = resolve_landmark(target_path, args.landmark)
    else:
        if args.x is None or args.y is None:
            raise fail("both --x and --y are required when not using --landmark")
        x, y = args.x, args.y
    return scale_coords(session, x, y)


# VNC mouse button mapping
BUTTON_MAP: dict[str, int] = {"left": 1, "right": 3, "middle": 2}

# vncdotool KEYMAP uses short lowercase names (esc, bsp, del, pgup, pgdn, etc).
# Map common long-form names to vncdotool's expected short forms.
KEYSYM_ALIASES: dict[str, str] = {
    "escape": "esc",
    "backspace": "bsp",
    "delete": "del",
    "insert": "ins",
    "pageup": "pgup",
    "pagedown": "pgdn",
}


def normalize_key(name: str) -> str:
    """Map a user-friendly key name to the vncdotool KEYMAP name."""
    lower = name.strip().lower()
    return KEYSYM_ALIASES.get(lower, lower)


# ---------------------------------------------------------------------------
# tart exec
# ---------------------------------------------------------------------------


def tart_exec(
    vm_name: str, command: str, *, timeout: int = 120
) -> subprocess.CompletedProcess[str]:
    """Run a command inside the guest via tart exec."""
    return subprocess.run(
        ["tart", "exec", vm_name, "bash", "-lc", command],
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def probe_tart_exec(vm_name: str) -> bool:
    """Check if tart exec is available for the given VM."""
    try:
        result = tart_exec(vm_name, "echo __TART_EXEC_OK__", timeout=10)
        return "__TART_EXEC_OK__" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# ---------------------------------------------------------------------------
# VNC interaction helpers
# ---------------------------------------------------------------------------


def vnc_click(
    vnc_host: str, vnc_port: int, vnc_password: str, x: int, y: int, button: int = 1
) -> None:
    """Click at (x, y) via VNC. button: 1=left, 2=middle, 3=right."""
    client = None
    try:
        client = api.connect(f"{vnc_host}::{vnc_port}", password=vnc_password, timeout=12)
        client.mouseMove(x, y)
        client.mousePress(button)
        client.disconnect()
    finally:
        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass
        try:
            api.shutdown()
        except Exception:
            pass


def vnc_type_string(
    vnc_host: str, vnc_port: int, vnc_password: str, text: str
) -> None:
    """Type a string via VNC, handling special characters."""
    client = None
    try:
        client = api.connect(f"{vnc_host}::{vnc_port}", password=vnc_password, timeout=12)
        for ch in text:
            if ch == " ":
                client.keyPress("space")
            elif ch == "\n":
                client.keyPress("return")
            elif ch == "\t":
                client.keyPress("tab")
            else:
                client.keyPress(ch)
        client.disconnect()
    finally:
        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass
        try:
            api.shutdown()
        except Exception:
            pass


def vnc_send_keys(
    vnc_host: str, vnc_port: int, vnc_password: str, keys: str
) -> None:
    """Send a key combination via VNC (e.g. 'meta+space', 'ctrl+shift+a')."""
    parts = [normalize_key(k) for k in keys.split("+")]
    if not parts:
        return

    modifiers = parts[:-1]
    final_key = parts[-1]

    client = None
    try:
        client = api.connect(f"{vnc_host}::{vnc_port}", password=vnc_password, timeout=12)
        for mod in modifiers:
            client.keyDown(mod)
        client.keyPress(final_key)
        for mod in reversed(modifiers):
            client.keyUp(mod)
        client.disconnect()
    finally:
        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass
        try:
            api.shutdown()
        except Exception:
            pass


def tart_stop(vm_name: str, timeout_seconds: int) -> None:
    run_command(["tart", "stop", vm_name, "--timeout", str(timeout_seconds)], check=False)


def tart_delete(vm_name: str) -> None:
    run_command(["tart", "delete", vm_name], check=False)


def parse_subnet_prefix(interface: str) -> str:
    result = run_command(["ipconfig", "getifaddr", interface], check=True)
    ip = result.stdout.strip()
    parts = ip.split(".")
    if len(parts) != 4:
        raise fail(f"could not parse IP for interface {interface}: {ip!r}")
    return ".".join(parts[:3])


def find_open_ssh_hosts(prefix: str) -> list[str]:
    candidates = [f"{prefix}.{index}" for index in range(2, 255)]

    def is_open(ip: str) -> bool:
        try:
            with socket.create_connection((ip, 22), timeout=0.35):
                return True
        except OSError:
            return False

    open_hosts: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=96) as executor:
        future_to_ip = {executor.submit(is_open, ip): ip for ip in candidates}
        for future in concurrent.futures.as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                if future.result():
                    open_hosts.append(ip)
            except Exception:
                continue

    return sorted(open_hosts)


def host_matches_target(ip: str, username: str, password: str, share_name: str) -> bool:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            ip,
            username=username,
            password=password,
            timeout=3,
            banner_timeout=3,
            auth_timeout=3,
            look_for_keys=False,
            allow_agent=False,
        )
        probe_cmd = (
            "set -euo pipefail; "
            f"test -d {shlex.quote(f'/Volumes/My Shared Files/{share_name}')}; "
            "echo __TART_HARNESS_OK__; "
            "whoami"
        )
        stdin, stdout, stderr = client.exec_command(probe_cmd, timeout=4)
        lines = [line.strip() for line in stdout.read().decode("utf-8", errors="replace").splitlines()]
        return len(lines) >= 2 and lines[0] == "__TART_HARNESS_OK__" and lines[1] == username
    except Exception:
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


def discover_ssh_host(prefix: str, username: str, password: str, share_name: str) -> str:
    open_hosts = find_open_ssh_hosts(prefix)
    log(f"Open SSH hosts on {prefix}.0/24: {len(open_hosts)}")

    for ip in open_hosts:
        if host_matches_target(ip, username, password, share_name):
            return ip

    raise fail(
        "could not find target VM over SSH; pass --ssh-host manually or verify Remote Login + credentials"
    )


def capture_frame(
    vnc_host: str,
    vnc_port: int,
    vnc_password: str,
    output_path: Path,
    *,
    max_dimension: int = 0,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    last_error = ""
    backoff = 0.4
    for attempt in range(5):
        client = None
        try:
            client = api.connect(f"{vnc_host}::{vnc_port}", password=vnc_password, timeout=12)
            client.captureScreen(str(output_path))
            client.disconnect()
            api.shutdown()

            if output_path.exists():
                img = Image.open(output_path)
                w, h = img.size
                log(f"Captured {output_path.name} ({output_path.stat().st_size} bytes, {w}x{h})")
                if max_dimension and max(w, h) > max_dimension:
                    img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
                    img.save(str(output_path), format="PNG")
                    log(f"Resized to {img.size[0]}x{img.size[1]}")
                img.close()
            return
        except Exception as exc:
            last_error = str(exc)
            try:
                if client is not None:
                    client.disconnect()
            except Exception:
                pass
            try:
                api.shutdown()
            except Exception:
                pass
            if attempt < 4:
                time.sleep(backoff)
                backoff *= 2

    raise fail(f"failed VNC capture after retries: {last_error}")


def _capture_within_session(
    client: Any, output_path: Path, *, max_dimension: int = 0
) -> None:
    """Capture a frame using an already-connected VNC client (for batch use)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client.captureScreen(str(output_path))
    if output_path.exists():
        img = Image.open(output_path)
        w, h = img.size
        log(f"Captured {output_path.name} ({output_path.stat().st_size} bytes, {w}x{h})")
        if max_dimension and max(w, h) > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
            img.save(str(output_path), format="PNG")
            log(f"Resized to {img.size[0]}x{img.size[1]}")
        img.close()


def command_start(args: argparse.Namespace) -> int:
    require_command("tart")

    ensure_vm_exists(args.base_vm)

    ts = time.strftime("%Y%m%d-%H%M%S")
    run_vm = args.run_vm or f"{args.vm_prefix}-{ts}"

    if vm_exists(run_vm):
        raise fail(f"run VM already exists: {run_vm}")

    output_dir = Path(args.output_dir or f"./output/tart-harness/{ts}").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "tart-run.log"
    session_path = output_dir / "session.json"

    log(f"Cloning {args.base_vm} -> {run_vm}")
    run_command(["tart", "clone", args.base_vm, run_vm], check=True)

    log_handle = log_path.open("w", encoding="utf-8")
    process: subprocess.Popen[str] | None = None

    try:
        log(f"Starting VM {run_vm} (headless by default)")
        process = subprocess.Popen(
            [
                "tart",
                "run",
                "--vnc-experimental",
                f"--net-bridged={args.bridge_interface}",
                "--dir",
                f"{args.share_name}:{Path(args.share_path).resolve()}",
                run_vm,
            ],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )

        vnc_url = wait_for_vnc_url(log_path, process, timeout_seconds=args.vnc_wait_seconds)
        parsed = urlparse(vnc_url)
        vnc_host = parsed.hostname or "127.0.0.1"
        vnc_port = parsed.port
        vnc_password = parsed.password or ""

        if vnc_port is None or not vnc_password:
            raise fail(f"failed to parse VNC endpoint from URL: {vnc_url}")

        if args.open_vnc:
            run_command(["open", vnc_url], check=False)
            log("Opened VNC viewer")

        # Probe tart exec availability
        tart_exec_ok = probe_tart_exec(run_vm)
        log(f"tart exec available: {tart_exec_ok}")

        session = {
            "status": "running",
            "created_at": ts,
            "base_vm": args.base_vm,
            "run_vm": run_vm,
            "bridge_interface": args.bridge_interface,
            "share_name": args.share_name,
            "share_path": str(Path(args.share_path).resolve()),
            "vnc_url": vnc_url,
            "vnc_host": vnc_host,
            "vnc_port": vnc_port,
            "vnc_password": vnc_password,
            "open_vnc": args.open_vnc,
            "run_pid": process.pid,
            "log_path": str(log_path),
            "session_file": str(session_path),
            "tart_exec_available": tart_exec_ok,
        }

        # Probe framebuffer dimensions via a capture
        try:
            probe_path = output_dir / ".probe-capture.png"
            capture_frame(vnc_host, vnc_port, vnc_password, probe_path)
            if probe_path.exists():
                img = Image.open(probe_path)
                w, h = img.size
                img.close()
                session["framebuffer_width"] = w
                session["framebuffer_height"] = h
                log(f"Framebuffer: {w}x{h}")
                probe_path.unlink(missing_ok=True)
        except Exception:
            log("Could not probe framebuffer dimensions")

        # Coordinate scaling
        if args.logical_resolution:
            lw, lh = (int(v) for v in args.logical_resolution.split("x"))
            fb_w = session.get("framebuffer_width", lw)
            session["logical_width"] = lw
            session["logical_height"] = lh
            session["scale_factor"] = fb_w / lw
            log(f"Logical resolution: {lw}x{lh}, scale_factor: {session['scale_factor']}")

        save_session(session_path, session)
        print(json.dumps(session, indent=2))
        return 0
    except Exception:
        tart_stop(run_vm, timeout_seconds=8)
        if not args.keep_failed_vm:
            tart_delete(run_vm)
        raise
    finally:
        try:
            log_handle.close()
        except Exception:
            pass


def command_discover_ssh(args: argparse.Namespace) -> int:
    session_path = Path(args.session_file).resolve()
    session = load_session(session_path)

    run_vm = session.get("run_vm", "")

    # Try tart exec first to check if SSH is enabled
    if run_vm and session.get("tart_exec_available", False):
        try:
            result = tart_exec(run_vm, "systemsetup -getremotelogin", timeout=10)
            output = result.stdout.strip()
            if "Off" in output:
                log(
                    f"WARNING: Remote Login is OFF in guest. "
                    f"Enable it with: {__file__} enable-ssh "
                    f"--session-file {session_path}"
                )
        except Exception:
            pass

    prefix = parse_subnet_prefix(args.bridge_interface or session.get("bridge_interface", "en0"))
    share_name = args.share_name or session.get("share_name", "workspaces")

    log("Discovering target VM SSH host")
    ssh_host = discover_ssh_host(
        prefix=prefix,
        username=args.ssh_user,
        password=args.ssh_password,
        share_name=share_name,
    )

    session["ssh_host"] = ssh_host
    session["ssh_user"] = args.ssh_user
    save_session(session_path, session)
    print(ssh_host)
    return 0


def command_capture(args: argparse.Namespace) -> int:
    session = load_session(Path(args.session_file).resolve())
    capture_frame(
        vnc_host=session["vnc_host"],
        vnc_port=int(session["vnc_port"]),
        vnc_password=session["vnc_password"],
        output_path=Path(args.output).resolve(),
        max_dimension=args.max_dimension,
    )
    print(str(Path(args.output).resolve()))
    return 0


def command_exec(args: argparse.Namespace) -> int:
    session_path = Path(args.session_file).resolve()
    session = load_session(session_path)
    run_vm = session.get("run_vm")
    if not run_vm:
        raise fail(f"session missing run_vm: {session_path}")

    cmd_args = args.command_args
    if cmd_args and cmd_args[0] == "--":
        cmd_args = cmd_args[1:]
    command = " ".join(cmd_args)
    if not command:
        raise fail("no command provided")

    log(f"Executing in {run_vm}: {command}")

    # Try tart exec first
    try:
        result = tart_exec(run_vm, command, timeout=args.timeout)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode
    except subprocess.TimeoutExpired:
        log(f"tart exec timed out after {args.timeout}s")
    except FileNotFoundError:
        log("tart exec not available")

    # Fallback to SSH
    ssh_host = session.get("ssh_host")
    if not ssh_host:
        raise fail("tart exec failed and no ssh_host in session; run discover-ssh first")

    log(f"Falling back to SSH ({ssh_host})")
    ssh_user = session.get("ssh_user", "admin")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            ssh_host,
            username=ssh_user,
            password="admin",
            timeout=5,
            look_for_keys=False,
            allow_agent=False,
        )
        stdin, stdout, stderr = client.exec_command(command, timeout=args.timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()
        if out:
            print(out, end="")
        if err:
            print(err, end="", file=sys.stderr)
        return rc
    finally:
        client.close()


def command_click(args: argparse.Namespace) -> int:
    session = load_session(Path(args.session_file).resolve())
    x, y = resolve_click_coords(args, session)
    button = BUTTON_MAP.get(getattr(args, "button", "left"), 1)
    log(f"VNC click at ({x}, {y}) button={button}")
    vnc_click(
        session["vnc_host"],
        int(session["vnc_port"]),
        session["vnc_password"],
        x,
        y,
        button=button,
    )
    if args.capture:
        time.sleep(args.capture_delay)
        log(f"Capturing post-click frame to {args.capture}")
        capture_frame(
            session["vnc_host"],
            int(session["vnc_port"]),
            session["vnc_password"],
            Path(args.capture).resolve(),
        )
    return 0


def command_type_string(args: argparse.Namespace) -> int:
    session = load_session(Path(args.session_file).resolve())
    log(f"VNC type: {args.text!r}")
    vnc_type_string(
        session["vnc_host"],
        int(session["vnc_port"]),
        session["vnc_password"],
        args.text,
    )
    return 0


def command_send_keys(args: argparse.Namespace) -> int:
    session = load_session(Path(args.session_file).resolve())
    log(f"VNC send keys: {args.keys}")
    vnc_send_keys(
        session["vnc_host"],
        int(session["vnc_port"]),
        session["vnc_password"],
        args.keys,
    )
    return 0


def command_double_click(args: argparse.Namespace) -> int:
    session = load_session(Path(args.session_file).resolve())
    x, y = resolve_click_coords(args, session)
    button = BUTTON_MAP.get(getattr(args, "button", "left"), 1)
    log(f"VNC double-click at ({x}, {y}) button={button}")
    client = None
    try:
        client = api.connect(
            f"{session['vnc_host']}::{int(session['vnc_port'])}",
            password=session["vnc_password"],
            timeout=12,
        )
        client.mouseMove(x, y)
        client.mousePress(button)
        time.sleep(0.05)
        client.mousePress(button)
        client.disconnect()
    finally:
        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass
        try:
            api.shutdown()
        except Exception:
            pass
    if args.capture:
        time.sleep(args.capture_delay)
        capture_frame(
            session["vnc_host"],
            int(session["vnc_port"]),
            session["vnc_password"],
            Path(args.capture).resolve(),
        )
    return 0


def command_scroll(args: argparse.Namespace) -> int:
    session = load_session(Path(args.session_file).resolve())
    x, y = scale_coords(session, args.x, args.y)
    scroll_button = 4 if args.direction == "up" else 5
    log(f"VNC scroll {args.direction} x{args.clicks} at ({x}, {y})")
    client = None
    try:
        client = api.connect(
            f"{session['vnc_host']}::{int(session['vnc_port'])}",
            password=session["vnc_password"],
            timeout=12,
        )
        client.mouseMove(x, y)
        for _ in range(args.clicks):
            client.mousePress(scroll_button)
        client.disconnect()
    finally:
        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass
        try:
            api.shutdown()
        except Exception:
            pass
    return 0


def command_drag(args: argparse.Namespace) -> int:
    session = load_session(Path(args.session_file).resolve())
    fx, fy = scale_coords(session, args.from_x, args.from_y)
    tx, ty = scale_coords(session, args.to_x, args.to_y)
    log(f"VNC drag ({fx},{fy}) -> ({tx},{ty})")
    client = None
    try:
        client = api.connect(
            f"{session['vnc_host']}::{int(session['vnc_port'])}",
            password=session["vnc_password"],
            timeout=12,
        )
        client.mouseMove(fx, fy)
        client.mouseDown(1)
        client.mouseMove(tx, ty)
        client.mouseUp(1)
        client.disconnect()
    finally:
        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass
        try:
            api.shutdown()
        except Exception:
            pass
    if args.capture:
        time.sleep(args.capture_delay)
        capture_frame(
            session["vnc_host"],
            int(session["vnc_port"]),
            session["vnc_password"],
            Path(args.capture).resolve(),
        )
    return 0


def _resolve_batch_coords(
    step: dict[str, Any],
    session: dict[str, Any],
    landmarks: dict[str, dict[str, int]],
    step_index: int,
) -> tuple[int, int]:
    """Resolve coordinates from a batch step (landmark or x/y)."""
    if "landmark" in step:
        name = step["landmark"]
        if name not in landmarks:
            raise fail(f"landmark {name!r} not found at step {step_index}")
        lm = landmarks[name]
        x, y = lm.get("x"), lm.get("y")
        if x is None or y is None:
            raise fail(f"landmark {name!r} missing x or y at step {step_index}")
        x, y = int(x), int(y)
    elif "x" in step and "y" in step:
        x, y = int(step["x"]), int(step["y"])
    else:
        raise fail(f"step {step_index}: provide 'landmark' or both 'x' and 'y'")
    return scale_coords(session, x, y)


def command_batch(args: argparse.Namespace) -> int:
    session = load_session(Path(args.session_file).resolve())

    if args.steps_file:
        steps_data = json.loads(Path(args.steps_file).read_text(encoding="utf-8"))
    elif args.steps_json:
        steps_data = json.loads(args.steps_json)
    else:
        raise fail("provide --steps-file or --steps-json")

    steps = steps_data.get("steps", [])
    if not steps:
        raise fail("no steps in batch input")

    # Load landmarks once for the whole batch
    landmarks: dict[str, dict[str, int]] = {}
    if args.target and Path(args.target).exists():
        target_data = yaml.safe_load(Path(args.target).read_text(encoding="utf-8"))
        landmarks = target_data.get("landmarks", {})

    log(f"Batch: {len(steps)} steps in single VNC connection")
    client = None
    try:
        client = api.connect(
            f"{session['vnc_host']}::{int(session['vnc_port'])}",
            password=session["vnc_password"],
            timeout=12,
        )

        for i, step in enumerate(steps):
            action = step.get("action", "")
            log(f"  step {i}: {action}")

            if action == "click":
                x, y = _resolve_batch_coords(step, session, landmarks, i)
                button = BUTTON_MAP.get(step.get("button", "left"), 1)
                client.mouseMove(x, y)
                client.mousePress(button)

            elif action == "double-click":
                x, y = _resolve_batch_coords(step, session, landmarks, i)
                button = BUTTON_MAP.get(step.get("button", "left"), 1)
                client.mouseMove(x, y)
                client.mousePress(button)
                time.sleep(0.05)
                client.mousePress(button)

            elif action == "type":
                text = step.get("text", "")
                for ch in text:
                    if ch == " ":
                        client.keyPress("space")
                    elif ch == "\n":
                        client.keyPress("return")
                    elif ch == "\t":
                        client.keyPress("tab")
                    else:
                        client.keyPress(ch)

            elif action == "send-keys":
                keys = step.get("keys")
                if not keys:
                    raise fail(f"step {i}: 'send-keys' requires 'keys' field")
                parts = [normalize_key(k) for k in keys.split("+")]
                modifiers, final_key = parts[:-1], parts[-1]
                for mod in modifiers:
                    client.keyDown(mod)
                client.keyPress(final_key)
                for mod in reversed(modifiers):
                    client.keyUp(mod)

            elif action == "scroll":
                x, y = _resolve_batch_coords(step, session, landmarks, i)
                scroll_button = 4 if step.get("direction", "down") == "up" else 5
                client.mouseMove(x, y)
                for _ in range(int(step.get("clicks", 1))):
                    client.mousePress(scroll_button)

            elif action == "drag":
                for field in ("from_x", "from_y", "to_x", "to_y"):
                    if field not in step:
                        raise fail(f"step {i}: 'drag' requires '{field}' field")
                fx, fy = scale_coords(session, int(step["from_x"]), int(step["from_y"]))
                tx, ty = scale_coords(session, int(step["to_x"]), int(step["to_y"]))
                client.mouseMove(fx, fy)
                client.mouseDown(1)
                client.mouseMove(tx, ty)
                client.mouseUp(1)

            elif action == "capture":
                output = step.get("output")
                if not output:
                    raise fail(f"step {i}: 'capture' requires 'output' field")
                out_path = Path(output).resolve()
                max_dim = int(step.get("max_dimension", 0))
                _capture_within_session(client, out_path, max_dimension=max_dim)

            elif action == "wait":
                seconds = min(float(step.get("seconds", 1)), 30.0)
                time.sleep(seconds)

            else:
                raise fail(f"unknown batch action: {action!r} at step {i}")

        client.disconnect()
    except Exception:
        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass
        raise
    finally:
        try:
            api.shutdown()
        except Exception:
            pass

    log("Batch complete")
    return 0


def command_enable_ssh(args: argparse.Namespace) -> int:
    session_path = Path(args.session_file).resolve()
    session = load_session(session_path)
    run_vm = session.get("run_vm")
    if not run_vm:
        raise fail(f"session missing run_vm: {session_path}")

    log("Checking Remote Login status via tart exec")
    result = tart_exec(run_vm, "systemsetup -getremotelogin", timeout=10)
    current = result.stdout.strip()
    log(f"Current: {current}")

    if "On" in current:
        log("Remote Login already enabled")
        return 0

    log("Enabling Remote Login")
    result = tart_exec(
        run_vm,
        "sudo systemsetup -setremotelogin on",
        timeout=15,
    )
    if result.returncode != 0:
        raise fail(f"Failed to enable Remote Login: {result.stderr.strip()}")

    # Verify
    result = tart_exec(run_vm, "systemsetup -getremotelogin", timeout=10)
    if "On" not in result.stdout:
        raise fail(f"Remote Login still off after enable: {result.stdout.strip()}")

    log("Remote Login enabled successfully")
    session["ssh_enabled_via_exec"] = True
    save_session(session_path, session)
    return 0


def command_status(args: argparse.Namespace) -> int:
    session_path = Path(args.session_file).resolve()
    session = load_session(session_path)
    run_vm = session.get("run_vm", "")

    status: dict[str, Any] = {"session_status": session.get("status", "unknown")}

    # Check VM exists
    status["vm_exists"] = vm_exists(run_vm) if run_vm else False

    # Check tart run process
    run_pid = session.get("run_pid")
    if isinstance(run_pid, int):
        try:
            os.kill(run_pid, 0)
            status["process_alive"] = True
        except OSError:
            status["process_alive"] = False
    else:
        status["process_alive"] = False

    # Check tart exec
    status["tart_exec_available"] = probe_tart_exec(run_vm) if run_vm else False

    # Check VNC
    vnc_host = session.get("vnc_host", "")
    vnc_port = session.get("vnc_port")
    if vnc_host and vnc_port:
        try:
            with socket.create_connection((vnc_host, int(vnc_port)), timeout=2):
                status["vnc_reachable"] = True
        except OSError:
            status["vnc_reachable"] = False
    else:
        status["vnc_reachable"] = False

    # Check SSH
    ssh_host = session.get("ssh_host")
    if ssh_host:
        try:
            with socket.create_connection((ssh_host, 22), timeout=2):
                status["ssh_reachable"] = True
        except OSError:
            status["ssh_reachable"] = False
    else:
        status["ssh_reachable"] = False

    print(json.dumps(status, indent=2))
    return 0


def command_teardown(args: argparse.Namespace) -> int:
    require_command("tart")

    session_path = Path(args.session_file).resolve()
    session = load_session(session_path)

    run_vm = session.get("run_vm")
    if not run_vm:
        raise fail(f"session missing run_vm: {session_path}")

    if args.close_vnc and session.get("open_vnc", False):
        log("Closing Screen Sharing before VM shutdown")
        close_screen_sharing()

    log(f"Stopping VM {run_vm}")
    tart_stop(run_vm, timeout_seconds=args.stop_timeout)

    if args.delete_vm:
        log(f"Deleting VM {run_vm}")
        tart_delete(run_vm)

    run_pid = session.get("run_pid")
    if isinstance(run_pid, int):
        try:
            os.kill(run_pid, 15)
        except OSError:
            pass

    session["status"] = "stopped"
    session["stopped_at"] = time.strftime("%Y%m%d-%H%M%S")
    session["delete_vm"] = args.delete_vm
    session["close_vnc"] = args.close_vnc
    save_session(session_path, session)
    print(json.dumps(session, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Headless-first Tart harness for GUI automation and capture"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="clone + run VM with VNC endpoint")
    start.add_argument("--base-vm", required=True)
    start.add_argument("--run-vm", default="")
    start.add_argument("--vm-prefix", default="tart-gui-run")
    start.add_argument("--bridge-interface", default="en0")
    start.add_argument("--share-name", default="workspaces")
    start.add_argument("--share-path", default=".")
    start.add_argument("--output-dir", default="")
    start.add_argument("--vnc-wait-seconds", type=int, default=60)
    start.add_argument("--keep-failed-vm", action="store_true")
    start.add_argument(
        "--open-vnc",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="open live Screen Sharing session (default: headless)",
    )
    start.add_argument(
        "--logical-resolution",
        default="",
        help="logical coordinate space (e.g. 1024x768). Omit for raw physical coords.",
    )
    start.set_defaults(func=command_start)

    discover = subparsers.add_parser(
        "discover-ssh",
        help="find target VM SSH host and store it in session.json",
    )
    discover.add_argument("--session-file", required=True)
    discover.add_argument("--bridge-interface", default="")
    discover.add_argument("--share-name", default="")
    discover.add_argument("--ssh-user", default="admin")
    discover.add_argument("--ssh-password", default="admin")
    discover.set_defaults(func=command_discover_ssh)

    capture = subparsers.add_parser("capture", help="capture one VNC frame")
    capture.add_argument("--session-file", required=True)
    capture.add_argument("--output", required=True)
    capture.add_argument(
        "--max-dimension",
        type=int,
        default=0,
        help="resize so longest edge is at most this many pixels",
    )
    capture.set_defaults(func=command_capture)

    # exec
    exec_cmd = subparsers.add_parser(
        "exec", help="run command in guest via tart exec (SSH fallback)"
    )
    exec_cmd.add_argument("--session-file", required=True)
    exec_cmd.add_argument("--timeout", type=int, default=120)
    exec_cmd.add_argument("command_args", nargs=argparse.REMAINDER, metavar="COMMAND")
    exec_cmd.set_defaults(func=command_exec)

    # click
    click = subparsers.add_parser("click", help="VNC mouse click")
    click.add_argument("--session-file", required=True)
    click_coords = click.add_mutually_exclusive_group(required=True)
    click_coords.add_argument("--landmark", help="landmark name from target manifest")
    click_coords.add_argument("--x", type=int, dest="x")
    click.add_argument("--y", type=int)
    click.add_argument("--target", default=".tart/target.yaml", help="target manifest path")
    click.add_argument("--button", choices=["left", "right", "middle"], default="left")
    click.add_argument("--capture", default="", help="capture frame after click to this path")
    click.add_argument("--capture-delay", type=float, default=0.5)
    click.set_defaults(func=command_click)

    # type-string
    type_str = subparsers.add_parser("type-string", help="type text via VNC")
    type_str.add_argument("--session-file", required=True)
    type_str.add_argument("--text", required=True)
    type_str.set_defaults(func=command_type_string)

    # send-keys
    send = subparsers.add_parser("send-keys", help="send key combination via VNC")
    send.add_argument("--session-file", required=True)
    send.add_argument("--keys", required=True, help="e.g. meta+space, ctrl+shift+a")
    send.set_defaults(func=command_send_keys)

    # double-click
    dblclick = subparsers.add_parser("double-click", help="VNC double-click")
    dblclick.add_argument("--session-file", required=True)
    dblclick_coords = dblclick.add_mutually_exclusive_group(required=True)
    dblclick_coords.add_argument("--landmark", help="landmark name from target manifest")
    dblclick_coords.add_argument("--x", type=int, dest="x")
    dblclick.add_argument("--y", type=int)
    dblclick.add_argument("--target", default=".tart/target.yaml")
    dblclick.add_argument("--button", choices=["left", "right", "middle"], default="left")
    dblclick.add_argument("--capture", default="")
    dblclick.add_argument("--capture-delay", type=float, default=0.5)
    dblclick.set_defaults(func=command_double_click)

    # scroll
    scroll_cmd = subparsers.add_parser("scroll", help="VNC scroll at position")
    scroll_cmd.add_argument("--session-file", required=True)
    scroll_cmd.add_argument("--x", type=int, required=True)
    scroll_cmd.add_argument("--y", type=int, required=True)
    scroll_cmd.add_argument("--direction", choices=["up", "down"], required=True)
    scroll_cmd.add_argument("--clicks", type=int, default=3)
    scroll_cmd.set_defaults(func=command_scroll)

    # drag
    drag_cmd = subparsers.add_parser("drag", help="VNC drag between two points")
    drag_cmd.add_argument("--session-file", required=True)
    drag_cmd.add_argument("--from-x", type=int, required=True)
    drag_cmd.add_argument("--from-y", type=int, required=True)
    drag_cmd.add_argument("--to-x", type=int, required=True)
    drag_cmd.add_argument("--to-y", type=int, required=True)
    drag_cmd.add_argument("--capture", default="")
    drag_cmd.add_argument("--capture-delay", type=float, default=0.5)
    drag_cmd.set_defaults(func=command_drag)

    # batch
    batch_cmd = subparsers.add_parser(
        "batch", help="run multiple VNC operations in a single connection"
    )
    batch_cmd.add_argument("--session-file", required=True)
    batch_cmd.add_argument("--steps-file", default="", help="path to JSON file with steps")
    batch_cmd.add_argument("--steps-json", default="", help="inline JSON with steps")
    batch_cmd.add_argument("--target", default=".tart/target.yaml", help="target manifest path")
    batch_cmd.set_defaults(func=command_batch)

    # enable-ssh
    enable_ssh = subparsers.add_parser("enable-ssh", help="enable Remote Login via tart exec")
    enable_ssh.add_argument("--session-file", required=True)
    enable_ssh.set_defaults(func=command_enable_ssh)

    # status
    status = subparsers.add_parser("status", help="check VM/VNC/SSH health")
    status.add_argument("--session-file", required=True)
    status.set_defaults(func=command_status)

    teardown = subparsers.add_parser(
        "teardown",
        help="close VNC (optional), stop VM, then delete VM (optional)",
    )
    teardown.add_argument("--session-file", required=True)
    teardown.add_argument("--stop-timeout", type=int, default=20)
    teardown.add_argument(
        "--delete-vm",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    teardown.add_argument(
        "--close-vnc",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="close Screen Sharing first when open-vnc was used",
    )
    teardown.set_defaults(func=command_teardown)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return int(args.func(args))
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
