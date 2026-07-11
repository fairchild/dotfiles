#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Host a local web console for tuning the vocal skill."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_helpers import get_elevenlabs_api_key, load_dotenv

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
DEFAULT_DATA_DIR = SKILL_DIR / "data"
PREFERENCES_FILE = "preferences.json"

DEFAULT_PREFERENCES: dict[str, Any] = {
    "ttsProvider": "local",
    "sttProvider": "local",
    "sampleText": "Build complete. This is the current vocal tuning sample.",
    "localVoice": "Alex",
    "localRate": 190,
    "useMacSpeaker": False,
    "elevenlabsVoice": "George",
    "elevenlabsTtsModel": "eleven_flash_v2_5",
    "localSttModel": "mlx-community/whisper-base-mlx",
    "elevenlabsSttModel": "scribe_v2",
    "recordSeconds": 5,
}

LOCAL_VOICE_LINE_RE = re.compile(r"^(?P<name>.+?)\s{2,}(?P<locale>[a-z]{2}_[A-Z]{2})\b")

TTS_SCRIPTS = {
    "local": SCRIPTS_DIR / "tts_local.py",
    "elevenlabs": SCRIPTS_DIR / "tts_elevenlabs.py",
}

STT_SCRIPTS = {
    "local": SCRIPTS_DIR / "stt_local.py",
    "elevenlabs": SCRIPTS_DIR / "stt_elevenlabs.py",
}


class VocalConsoleError(Exception):
    """Expected user-facing API error."""

    def __init__(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int
    elapsed_ms: int


def data_dir_from_env() -> Path:
    raw = os.environ.get("VOCAL_DATA_DIR")
    return Path(raw).expanduser().resolve() if raw else DEFAULT_DATA_DIR


def preferences_path(data_dir: Path) -> Path:
    return data_dir / PREFERENCES_FILE


def sanitize_preferences(raw: dict[str, Any]) -> dict[str, Any]:
    prefs = dict(DEFAULT_PREFERENCES)

    def clean_str(key: str, max_len: int = 500) -> None:
        value = raw.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                prefs[key] = stripped[:max_len]

    for provider_key in ("ttsProvider", "sttProvider"):
        value = raw.get(provider_key)
        if value in {"local", "elevenlabs"}:
            prefs[provider_key] = value

    clean_str("sampleText", 4000)
    clean_str("localVoice", 120)
    clean_str("elevenlabsVoice", 160)
    clean_str("elevenlabsTtsModel", 160)
    clean_str("localSttModel", 220)
    clean_str("elevenlabsSttModel", 160)

    try:
        prefs["localRate"] = max(80, min(360, int(raw.get("localRate", prefs["localRate"]))))
    except (TypeError, ValueError):
        pass

    try:
        prefs["recordSeconds"] = max(1, min(60, int(raw.get("recordSeconds", prefs["recordSeconds"]))))
    except (TypeError, ValueError):
        pass

    prefs["useMacSpeaker"] = bool(raw.get("useMacSpeaker", prefs["useMacSpeaker"]))
    return prefs


def load_preferences(data_dir: Path) -> dict[str, Any]:
    path = preferences_path(data_dir)
    if not path.exists():
        return dict(DEFAULT_PREFERENCES)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_PREFERENCES)
    return sanitize_preferences(payload if isinstance(payload, dict) else {})


def save_preferences(data_dir: Path, raw: dict[str, Any]) -> dict[str, Any]:
    prefs = sanitize_preferences(raw)
    data_dir.mkdir(parents=True, exist_ok=True)
    preferences_path(data_dir).write_text(json.dumps(prefs, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return prefs


def run_command(cmd: list[str], timeout: int = 120) -> CommandResult:
    started = time.monotonic()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return CommandResult(False, stdout, stderr or f"timeout after {timeout}s", 124, elapsed_ms)
    except OSError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return CommandResult(False, "", str(exc), 1, elapsed_ms)

    elapsed_ms = int((time.monotonic() - started) * 1000)
    return CommandResult(result.returncode == 0, result.stdout.strip(), result.stderr.strip(), result.returncode, elapsed_ms)


def command_payload(result: CommandResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "elapsedMs": result.elapsed_ms,
    }


def parse_local_voices(output: str) -> list[dict[str, str]]:
    voices: list[dict[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        match = LOCAL_VOICE_LINE_RE.match(line)
        name = (match.group("name") if match else line.split("#", 1)[0]).strip()
        if name:
            voices.append({"name": name, "id": name, "detail": line.strip()})
    return voices


def parse_tabbed_voices(output: str) -> list[dict[str, str]]:
    voices: list[dict[str, str]] = []
    for line in output.splitlines():
        name, _, voice_id = line.partition("\t")
        name = name.strip()
        voice_id = voice_id.strip()
        if name:
            voices.append({"name": name, "id": voice_id or name, "detail": line.strip()})
    return voices


def parse_content_disposition(headers_text: str) -> tuple[str, str | None]:
    disposition = ""
    for line in headers_text.splitlines():
        if line.lower().startswith("content-disposition:"):
            disposition = line
            break

    name = ""
    filename: str | None = None
    for item in disposition.split(";"):
        item = item.strip()
        if item.startswith("name="):
            name = item.split("=", 1)[1].strip('"')
        elif item.startswith("filename="):
            filename = item.split("=", 1)[1].strip('"') or None
    return name, filename


def provider_script(kind: str, provider: str) -> Path:
    scripts = TTS_SCRIPTS if kind == "tts" else STT_SCRIPTS
    script = scripts.get(provider)
    if script is None:
        raise VocalConsoleError(f"Unsupported {kind} provider: {provider}")
    return script


def run_provider_check(kind: str, provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    script = provider_script(kind, provider)
    cmd = ["uv", "run", "--script", str(script), "--check"]
    if kind == "stt" and provider == "local":
        model = str(payload.get("model") or DEFAULT_PREFERENCES["localSttModel"]).strip()
        if model:
            cmd.extend(["--model", model])
    result = run_command(cmd, timeout=300)
    return command_payload(result)


def list_voices(provider: str) -> dict[str, Any]:
    script = provider_script("tts", provider)
    result = run_command(["uv", "run", "--script", str(script), "--list-voices"], timeout=120)
    if not result.ok:
        return {"ok": False, "voices": [], **command_payload(result)}

    voices = parse_local_voices(result.stdout) if provider == "local" else parse_tabbed_voices(result.stdout)
    return {"ok": True, "voices": voices, **command_payload(result)}


def synthesize(payload: dict[str, Any]) -> tuple[bytes, str, dict[str, Any]]:
    provider = str(payload.get("provider") or "local")
    text = str(payload.get("text") or "").strip()
    if not text:
        raise VocalConsoleError("Text is required")

    script = provider_script("tts", provider)
    suffix = ".m4a" if provider == "local" else ".mp3"
    media_type = "audio/mp4" if provider == "local" else "audio/mpeg"

    with tempfile.NamedTemporaryFile(prefix="vocal-web-tts-", suffix=suffix, delete=False) as temp:
        output_path = Path(temp.name)

    try:
        cmd = ["uv", "run", "--script", str(script), "--text", text, "--output", str(output_path)]
        if provider == "local":
            voice = str(payload.get("voice") or "").strip()
            rate = payload.get("rate")
            if voice:
                cmd.extend(["--voice", voice])
            if rate not in (None, ""):
                cmd.extend(["--rate", str(rate)])
        else:
            voice = str(payload.get("voice") or DEFAULT_PREFERENCES["elevenlabsVoice"]).strip()
            model = str(payload.get("model") or DEFAULT_PREFERENCES["elevenlabsTtsModel"]).strip()
            if voice:
                cmd.extend(["--voice", voice])
            if model:
                cmd.extend(["--model", model])

        result = run_command(cmd, timeout=300)
        if not result.ok:
            raise VocalConsoleError(result.stderr or result.stdout or "TTS command failed", HTTPStatus.BAD_GATEWAY)
        if bool(payload.get("useMacSpeaker")) and provider == "local":
            speaker_cmd = ["uv", "run", "--script", str(script), "--text", text]
            voice = str(payload.get("voice") or "").strip()
            rate = payload.get("rate")
            if voice:
                speaker_cmd.extend(["--voice", voice])
            if rate not in (None, ""):
                speaker_cmd.extend(["--rate", str(rate)])
            _ = run_command(speaker_cmd, timeout=120)
        audio = output_path.read_bytes()
        return audio, media_type, command_payload(result)
    finally:
        output_path.unlink(missing_ok=True)


def transcribe(upload: bytes, filename: str, payload: dict[str, Any]) -> dict[str, Any]:
    provider = str(payload.get("provider") or "local")
    script = provider_script("stt", provider)
    suffix = Path(filename).suffix or mimetypes.guess_extension(str(payload.get("contentType") or "")) or ".webm"

    with tempfile.NamedTemporaryFile(prefix="vocal-web-stt-", suffix=suffix, delete=False) as temp:
        temp.write(upload)
        audio_path = Path(temp.name)

    try:
        cmd = ["uv", "run", "--script", str(script), "--file", str(audio_path)]
        model = str(payload.get("model") or "").strip()
        if model:
            cmd.extend(["--model", model])
        result = run_command(cmd, timeout=600)
        return {"transcript": result.stdout if result.ok else "", **command_payload(result)}
    finally:
        audio_path.unlink(missing_ok=True)


def read_json_body(handler: BaseHTTPRequestHandler, max_bytes: int = 2_000_000) -> dict[str, Any]:
    length = int(handler.headers.get("content-length") or "0")
    if length > max_bytes:
        raise VocalConsoleError("Request body is too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
    raw = handler.rfile.read(length) if length else b"{}"
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise VocalConsoleError(f"Invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise VocalConsoleError("JSON object body is required")
    return payload


def parse_multipart_upload(handler: BaseHTTPRequestHandler, max_bytes: int = 40_000_000) -> tuple[bytes, str, dict[str, Any]]:
    content_type = handler.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise VocalConsoleError("multipart/form-data upload is required")
    boundary_token = "boundary="
    if boundary_token not in content_type:
        raise VocalConsoleError("multipart boundary is missing")
    boundary = content_type.split(boundary_token, 1)[1].strip().strip('"')
    if not boundary:
        raise VocalConsoleError("multipart boundary is empty")

    length = int(handler.headers.get("content-length") or "0")
    if length > max_bytes:
        raise VocalConsoleError("Uploaded audio is too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
    body = handler.rfile.read(length)
    delimiter = ("--" + boundary).encode("utf-8")
    fields: dict[str, Any] = {}
    file_bytes = b""
    filename = "recording.webm"

    for part in body.split(delimiter):
        part = part.strip()
        if not part or part == b"--":
            continue
        if part.endswith(b"--"):
            part = part[:-2].strip()
        headers_blob, sep, value = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers_text = headers_blob.decode("utf-8", errors="replace")
        value = value.removesuffix(b"\r\n")
        name, parsed_filename = parse_content_disposition(headers_text)
        if parsed_filename:
            filename = parsed_filename
        if not name:
            continue
        if name == "audio":
            file_bytes = value
        elif name == "payload":
            try:
                parsed = json.loads(value.decode("utf-8"))
                if isinstance(parsed, dict):
                    fields.update(parsed)
            except json.JSONDecodeError:
                fields["payload"] = value.decode("utf-8", errors="replace")
        else:
            fields[name] = value.decode("utf-8", errors="replace")

    if not file_bytes:
        raise VocalConsoleError("Audio upload is missing")
    return file_bytes, filename, fields


def json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_html() -> bytes:
    encoded_default = base64.b64encode(json.dumps(DEFAULT_PREFERENCES).encode("utf-8")).decode("ascii")
    return HTML_TEMPLATE.replace("__DEFAULT_PREFS_B64__", encoded_default).encode("utf-8")


def make_handler(data_dir: Path) -> type[BaseHTTPRequestHandler]:
    class VocalConsoleHandler(BaseHTTPRequestHandler):
        server_version = "VocalWebConsole/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

        def send_payload(self, payload: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            self.send_response(status)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(payload)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            self.send_payload(json_bytes(payload), "application/json; charset=utf-8", status)

        def send_error_json(self, message: str, status: HTTPStatus) -> None:
            self.send_json({"ok": False, "error": message}, status)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    self.send_payload(build_html(), "text/html; charset=utf-8")
                    return
                if parsed.path == "/api/preferences":
                    self.send_json({"ok": True, "preferences": load_preferences(data_dir), "path": str(preferences_path(data_dir))})
                    return
                if parsed.path == "/api/voices":
                    provider = parse_qs(parsed.query).get("provider", ["local"])[0]
                    self.send_json(list_voices(provider))
                    return
                if parsed.path == "/api/status":
                    api_key = get_elevenlabs_api_key()
                    self.send_json(
                        {
                            "ok": True,
                            "skillDir": str(SKILL_DIR),
                            "dataDir": str(data_dir),
                            "preferencesPath": str(preferences_path(data_dir)),
                            "hasUv": shutil.which("uv") is not None,
                            "hasSay": shutil.which("say") is not None,
                            "hasAfplay": shutil.which("afplay") is not None,
                            "hasElevenLabsKey": bool(api_key),
                        }
                    )
                    return
                self.send_error_json("Not found", HTTPStatus.NOT_FOUND)
            except VocalConsoleError as exc:
                self.send_error_json(str(exc), exc.status)
            except Exception as exc:
                self.send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/preferences":
                    prefs = save_preferences(data_dir, read_json_body(self))
                    self.send_json({"ok": True, "preferences": prefs, "path": str(preferences_path(data_dir))})
                    return
                if parsed.path == "/api/check":
                    payload = read_json_body(self)
                    kind = str(payload.get("kind") or "tts")
                    provider = str(payload.get("provider") or "local")
                    self.send_json(run_provider_check(kind, provider, payload))
                    return
                if parsed.path == "/api/synthesize":
                    payload = read_json_body(self)
                    audio, media_type, meta = synthesize(payload)
                    self.send_response(HTTPStatus.OK)
                    self.send_header("content-type", media_type)
                    self.send_header("content-length", str(len(audio)))
                    self.send_header("cache-control", "no-store")
                    self.send_header("x-vocal-command-ok", str(meta["ok"]).lower())
                    self.send_header("x-vocal-elapsed-ms", str(meta["elapsedMs"]))
                    self.end_headers()
                    self.wfile.write(audio)
                    return
                if parsed.path == "/api/transcribe":
                    upload, filename, payload = parse_multipart_upload(self)
                    self.send_json(transcribe(upload, filename, payload))
                    return
                self.send_error_json("Not found", HTTPStatus.NOT_FOUND)
            except VocalConsoleError as exc:
                self.send_error_json(str(exc), exc.status)
            except Exception as exc:
                self.send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    return VocalConsoleHandler


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vocal Console</title>
  <style>
    :root {
      color-scheme: light dark;
      --ink: #171512;
      --muted: #6d675f;
      --line: #d8d0c4;
      --paper: #fbf8f1;
      --panel: #fffdf8;
      --panel-2: #f4efe5;
      --accent: #266f63;
      --accent-2: #8b542f;
      --danger: #9a322b;
      --focus: #b77435;
      --shadow: rgba(32, 27, 19, 0.1);
      --grid-line-x: rgba(23, 21, 18, 0.045);
      --grid-line-y: rgba(23, 21, 18, 0.035);
      --panel-surface: rgba(255, 253, 248, 0.92);
      --button-border: #bfb5a7;
      --warning-border: #c98953;
      --warning-ink: #5b321a;
      --danger-border: #c5908a;
      --good-border: #8eb8ae;
      --bad-border: #d7a09b;
      --quick-copy: #efe6d8;
      --segmented: #ece5d8;
      --active-border: #d0c4b5;
      --meter-bg: #e5ddd0;
      --console-bg: #1d1a16;
      --console-ink: #f9f0dc;
      --drop-bg: rgba(244, 239, 229, 0.7);
      --control-bg: rgba(255, 253, 248, 0.72);
      --mono: "SFMono-Regular", "Menlo", "Consolas", monospace;
      --sans: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
    }

    @media (prefers-color-scheme: dark) {
      :root {
        --ink: #f3eadb;
        --muted: #b9ad9d;
        --line: #474035;
        --paper: #11100e;
        --panel: #1b1916;
        --panel-2: #242019;
        --accent: #45a997;
        --accent-2: #d08a57;
        --danger: #ef8e82;
        --focus: #dea365;
        --shadow: rgba(0, 0, 0, 0.38);
        --grid-line-x: rgba(255, 244, 225, 0.045);
        --grid-line-y: rgba(255, 244, 225, 0.035);
        --panel-surface: rgba(27, 25, 22, 0.94);
        --button-border: #665b4c;
        --warning-border: #9b6d4d;
        --warning-ink: #f3cba5;
        --danger-border: #8e5550;
        --good-border: #40796f;
        --bad-border: #895854;
        --quick-copy: #242019;
        --segmented: #2d281f;
        --active-border: #5b5042;
        --meter-bg: #302a22;
        --console-bg: #080806;
        --console-ink: #f7eddb;
        --drop-bg: rgba(37, 33, 28, 0.72);
        --control-bg: rgba(27, 25, 22, 0.75);
      }
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(90deg, var(--grid-line-x) 1px, transparent 1px),
        linear-gradient(180deg, var(--grid-line-y) 1px, transparent 1px),
        var(--paper);
      background-size: 28px 28px;
      color: var(--ink);
      font-family: var(--sans);
      letter-spacing: 0;
    }

    button, input, select, textarea {
      font: inherit;
    }

    button, input, select, textarea {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--ink);
    }

    button {
      min-height: 38px;
      padding: 0 13px;
      border-color: var(--button-border);
      cursor: pointer;
      font-weight: 650;
      transition: transform 120ms ease, border-color 120ms ease, background 120ms ease;
    }

    button:hover { transform: translateY(-1px); border-color: var(--accent); }
    button:disabled { cursor: not-allowed; opacity: 0.55; transform: none; }

    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: white;
    }

    button.warning {
      border-color: var(--warning-border);
      color: var(--warning-ink);
    }

    button.danger {
      border-color: var(--danger-border);
      color: var(--danger);
    }

    .wrap {
      width: min(1220px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 26px 0 40px;
    }

    header {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 18px;
      align-items: end;
      border-bottom: 2px solid var(--ink);
      padding-bottom: 18px;
      margin-bottom: 18px;
    }

    h1 {
      margin: 0;
      font-size: clamp(2rem, 5vw, 4.8rem);
      line-height: 0.9;
      letter-spacing: 0;
      font-weight: 850;
    }

    .subtitle {
      margin: 10px 0 0;
      color: var(--muted);
      max-width: 780px;
      font-size: 0.98rem;
    }

    .status-strip {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
      justify-content: flex-end;
      align-items: center;
      max-width: 520px;
    }

    .status-label {
      align-self: center;
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }

    .status-check {
      position: relative;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.78rem;
      white-space: nowrap;
    }

    .status-check.good { color: var(--accent); }
    .status-check.bad { color: var(--danger); }

    .status-check::before {
      content: "\2713";
      display: inline-grid;
      place-items: center;
      width: 1rem;
      height: 1rem;
      font-family: var(--sans);
      font-size: 0.82rem;
      font-weight: 850;
      line-height: 1;
    }

    .status-check.bad::before {
      content: "\25CB";
    }

    .status-check[data-tooltip]::after {
      content: attr(data-tooltip);
      position: absolute;
      z-index: 20;
      top: calc(100% + 8px);
      right: 0;
      width: max-content;
      max-width: min(280px, calc(100vw - 32px));
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--console-bg);
      color: var(--console-ink);
      box-shadow: 0 10px 22px var(--shadow);
      font-family: var(--sans);
      font-size: 0.78rem;
      font-weight: 600;
      line-height: 1.35;
      white-space: normal;
      opacity: 0;
      pointer-events: none;
      transform: translateY(-3px);
      transition: opacity 120ms ease, transform 120ms ease;
    }

    .status-check[data-tooltip]:hover::after,
    .status-check[data-tooltip]:focus-visible::after {
      opacity: 1;
      transform: translateY(0);
    }

    .grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 14px;
      align-items: start;
      max-width: 920px;
      margin: 0 auto;
    }

    .defaults-overview {
      display: grid;
      gap: 12px;
      max-width: 920px;
      margin: 0 auto 14px;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-left: 4px solid var(--accent);
      border-radius: 8px;
      background: var(--panel-surface);
      box-shadow: 0 10px 24px var(--shadow);
    }

    .defaults-copy {
      display: grid;
      gap: 5px;
    }

    .defaults-copy h2 {
      margin: 0;
      font-size: 1.08rem;
      letter-spacing: 0;
    }

    .defaults-copy p {
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
    }

    .defaults-meta {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      padding-top: 2px;
    }

    .defaults-path {
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.74rem;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }

    .defaults-state {
      color: var(--accent);
      font-family: var(--mono);
      font-size: 0.74rem;
      font-weight: 800;
      white-space: nowrap;
    }

    .defaults-preview {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin: 0;
    }

    .defaults-preview div {
      display: grid;
      gap: 5px;
      min-width: 0;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--control-bg);
    }

    .defaults-preview dt {
      color: var(--muted);
      font-size: 0.7rem;
      font-weight: 850;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }

    .defaults-preview dd {
      margin: 0;
      min-width: 0;
      color: var(--ink);
      font-weight: 750;
      line-height: 1.32;
      overflow-wrap: anywhere;
    }

    .defaults-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }

    .defaults-help {
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.4;
    }

    .panel {
      background: var(--panel-surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 14px 30px var(--shadow);
      overflow: hidden;
    }

    .quickstart {
      display: grid;
      grid-template-columns: 1fr;
      gap: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      overflow: hidden;
    }

    .quickstart-copy {
      padding: 18px;
      border-bottom: 1px solid var(--line);
      background: var(--quick-copy);
    }

    .quickstart-copy h2 {
      margin: 0;
      font-size: 1.35rem;
      letter-spacing: 0;
    }

    .quickstart-copy p {
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.45;
    }

    .quick-provider {
      display: grid;
      gap: 8px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: var(--control-bg);
    }

    .quick-provider label {
      max-width: 340px;
    }

    .quick-provider .console-line {
      color: var(--muted);
    }

    .quick-actions {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
      padding: 14px 16px;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }

    .quick-action {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
      align-content: center;
      min-height: 76px;
      padding: 16px 18px;
      border: 2px solid var(--accent);
      border-radius: 8px;
      text-align: left;
      box-shadow: 0 8px 0 rgba(18, 81, 72, 0.28), 0 14px 22px var(--shadow);
    }

    .quick-action:active {
      transform: translateY(3px);
      box-shadow: 0 4px 0 rgba(18, 81, 72, 0.28), 0 8px 16px var(--shadow);
    }

    .quick-action-copy {
      display: grid;
      gap: 6px;
      min-width: 0;
    }

    .quick-action-copy strong {
      display: block;
      font-size: 1.08rem;
      line-height: 1.15;
    }

    .quick-action-copy span {
      display: block;
      font-weight: 500;
      line-height: 1.35;
    }

    .quick-action.primary {
      background: var(--accent);
      color: white;
    }

    .quick-action.primary span {
      color: rgba(255, 255, 255, 0.78);
    }

    .quick-action-cue {
      display: inline-grid;
      place-items: center;
      min-width: 58px;
      min-height: 34px;
      padding: 0 10px;
      border: 1px solid rgba(255, 255, 255, 0.48);
      border-radius: 999px;
      color: white;
      font-size: 0.78rem;
      font-weight: 850;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .flow-status {
      padding: 10px 14px;
      border-top: 1px solid var(--line);
      background: var(--console-bg);
      color: var(--console-ink);
      font-family: var(--mono);
      font-size: 0.8rem;
    }

    .sample-player {
      display: grid;
      gap: 8px;
    }

    .sample-player-label {
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.78rem;
      line-height: 1.35;
    }

    .layer {
      background: var(--panel-surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 14px 30px var(--shadow);
      overflow: hidden;
    }

    .layer + .layer {
      margin-top: 0;
    }

    .layer summary {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 14px;
      align-items: center;
      padding: 17px 18px;
      cursor: pointer;
      background: var(--panel-2);
      border-bottom: 1px solid transparent;
      list-style: none;
    }

    .layer[open] summary {
      border-bottom-color: var(--line);
    }

    .layer summary::-webkit-details-marker {
      display: none;
    }

    .summary-copy {
      display: grid;
      gap: 5px;
      min-width: 0;
    }

    .summary-kicker {
      color: var(--accent);
      font-family: var(--mono);
      font-size: 0.72rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }

    .summary-title {
      margin: 0;
      font-size: 1.2rem;
      line-height: 1.1;
      letter-spacing: 0;
    }

    .summary-description {
      color: var(--muted);
      line-height: 1.4;
      max-width: 680px;
    }

    .summary-icon {
      position: relative;
      display: grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 50%;
      color: var(--muted);
      font-size: 0;
      font-weight: 800;
      transition: border-color 140ms ease, color 140ms ease, background 140ms ease;
    }

    .summary-icon::before {
      content: "+";
      font-size: 1.1rem;
      line-height: 1;
    }

    .layer[open] .summary-icon {
      color: var(--accent);
      border-color: var(--accent);
    }

    .layer[open] .summary-icon::before {
      content: "\2212";
    }

    .summary-icon::after {
      content: "Expand";
      position: absolute;
      z-index: 30;
      top: 50%;
      right: calc(100% + 8px);
      width: max-content;
      max-width: 140px;
      padding: 6px 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--console-bg);
      color: var(--console-ink);
      box-shadow: 0 8px 18px var(--shadow);
      font-family: var(--sans);
      font-size: 0.75rem;
      font-weight: 700;
      line-height: 1.2;
      opacity: 0;
      pointer-events: none;
      transform: translateY(-50%) translateX(3px);
      transition: opacity 120ms ease, transform 120ms ease;
    }

    .layer[open] .summary-icon::after {
      content: "Collapse";
    }

    .summary-icon:hover::after {
      opacity: 1;
      transform: translateY(-50%) translateX(0);
    }

    .layer-body {
      padding: 16px;
      display: grid;
      gap: 14px;
    }

    .guide-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .guide-note {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: var(--control-bg);
      line-height: 1.45;
    }

    .guide-note h3 {
      margin: 0 0 6px;
      font-size: 0.95rem;
      letter-spacing: 0;
    }

    .guide-note p {
      margin: 0;
      color: var(--muted);
    }

    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 13px 15px;
      background: var(--panel-2);
      border-bottom: 1px solid var(--line);
    }

    .panel-title {
      margin: 0;
      font-size: 0.86rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .panel-body {
      padding: 15px;
      display: grid;
      gap: 14px;
    }

    .segmented {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 4px;
      padding: 4px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--segmented);
    }

    .segmented button {
      min-height: 34px;
      border: 0;
      background: transparent;
      color: var(--muted);
      box-shadow: none;
    }

    .segmented button.active {
      background: var(--panel);
      color: var(--ink);
      border: 1px solid var(--active-border);
    }

    label {
      display: grid;
      gap: 6px;
      font-size: 0.78rem;
      color: var(--muted);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    input, select {
      min-height: 38px;
      padding: 0 10px;
      width: 100%;
    }

    textarea {
      width: 100%;
      min-height: 140px;
      padding: 12px;
      resize: vertical;
      line-height: 1.45;
    }

    .split {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }

    .toggle {
      display: grid;
      grid-template-columns: 17px minmax(0, 1fr);
      align-items: start;
      gap: 8px;
      color: var(--ink);
      text-transform: none;
      letter-spacing: 0;
      font-size: 0.9rem;
    }

    .toggle span {
      min-width: 0;
      line-height: 1.35;
    }

    .toggle input {
      width: 17px;
      height: 17px;
      min-height: 17px;
    }

    .meter {
      height: 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--meter-bg);
      overflow: hidden;
    }

    .meter span {
      display: block;
      width: 0%;
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--focus));
      transition: width 180ms ease;
    }

    audio {
      width: 100%;
      min-height: 42px;
    }

    pre {
      margin: 0;
      padding: 12px;
      overflow: auto;
      min-height: 72px;
      max-height: 220px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--console-bg);
      color: var(--console-ink);
      font-family: var(--mono);
      font-size: 0.78rem;
      line-height: 1.45;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .drop {
      display: grid;
      place-items: center;
      min-height: 102px;
      padding: 14px;
      border: 1px dashed #b8ab9a;
      border-radius: 8px;
      background: var(--drop-bg);
      text-align: center;
      color: var(--muted);
    }

    .drop input {
      width: min(100%, 310px);
      margin-top: 10px;
    }

    .console-line {
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.78rem;
      min-height: 18px;
    }

    .control-group {
      display: grid;
      gap: 10px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--control-bg);
    }

    .save-explainer,
    .save-path,
    .settings-preview-panel {
      display: grid;
      gap: 9px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--control-bg);
    }

    .save-explainer {
      border-left: 4px solid var(--accent);
    }

    .save-explainer strong,
    .settings-preview-head h3,
    .preview-label {
      margin: 0;
      font-size: 0.95rem;
      letter-spacing: 0;
    }

    .save-explainer p,
    .save-path small {
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
    }

    .save-path span,
    .settings-preview-head span {
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.72rem;
      line-height: 1.35;
    }

    .save-path code {
      display: block;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--ink);
      font-family: var(--mono);
      font-size: 0.78rem;
      line-height: 1.4;
      word-break: break-word;
    }

    .settings-preview-head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: baseline;
    }

    .settings-preview {
      display: grid;
      grid-template-columns: minmax(130px, 0.34fr) minmax(0, 1fr);
      gap: 8px 12px;
      margin: 0;
      padding-top: 3px;
    }

    .settings-preview dt {
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }

    .settings-preview dd {
      margin: 0;
      min-width: 0;
      color: var(--ink);
      font-weight: 700;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }

    .command-preview-block {
      display: grid;
      gap: 8px;
    }

    .hidden { display: none !important; }

    :focus-visible {
      outline: 3px solid rgba(183, 116, 53, 0.35);
      outline-offset: 2px;
    }

    @media (max-width: 860px) {
      .wrap { width: min(100vw - 22px, 720px); padding-top: 18px; }
      header,
      .split,
      .guide-grid,
      .settings-preview,
      .settings-preview-head,
      .defaults-meta,
      .defaults-preview {
        grid-template-columns: 1fr;
      }
      .status-strip { justify-content: flex-start; }
      .status-check[data-tooltip]::after { left: 0; right: auto; }
      .defaults-state { white-space: normal; }
      h1 { font-size: 3rem; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>Vocal Console</h1>
        <p class="subtitle">Preview voices here. Save defaults to parameterize how the vocal skill speaks and listens in future runs.</p>
      </div>
      <div class="status-strip" id="statusStrip">
        <span class="status-check">loading status</span>
      </div>
    </header>

    <section class="defaults-overview" id="defaultsOverview" aria-labelledby="defaultsTitle">
      <div class="defaults-copy">
        <span class="summary-kicker">Saved defaults</span>
        <h2 id="defaultsTitle">These are the preferences the vocal skill will start from</h2>
        <p>They are loaded from a local file. Change any controls below to try new values, then use Save as skill defaults to replace the saved file.</p>
      </div>
      <div class="defaults-meta">
        <div class="defaults-path" id="defaultsPath">Preference file: loading...</div>
        <div class="defaults-state" id="defaultsSavedState">Loading saved preferences...</div>
      </div>
      <dl class="defaults-preview" id="defaultsPreview"></dl>
      <div class="defaults-actions">
        <button id="reviewSaveDefaults" type="button">Review and save defaults</button>
        <span class="defaults-help" id="defaultsHelp">The first layer previews changes. Saving is the step that makes them the future default.</span>
      </div>
    </section>

    <main class="grid">
      <details class="layer panel" data-section-key="try" open>
        <summary>
            <span class="summary-copy">
              <span class="summary-kicker">Start here</span>
              <span class="summary-title">Try one speech sample</span>
            <span class="summary-description">Preview changes without committing them. Saving later updates the skill defaults.</span>
            </span>
          <span class="summary-icon" aria-hidden="true">+</span>
        </summary>
        <div class="layer-body">
          <label>Sample text
            <textarea id="sampleText"></textarea>
          </label>
          <section class="quickstart" aria-labelledby="quickstartTitle">
            <div class="quickstart-copy">
              <h2 id="quickstartTitle">First prove the loop</h2>
              <p>Choose a provider, click once, and listen. Nothing changes outside this page until you save defaults.</p>
            </div>
            <div class="quick-provider">
              <label>Speech provider
                <select id="quickTtsProvider">
                  <option value="local">Local macOS say</option>
                  <option value="elevenlabs">ElevenLabs cloud</option>
                </select>
              </label>
              <div class="console-line" id="quickProviderHint">Local macOS speech. No account required.</div>
            </div>
            <div class="quick-actions">
              <button id="quickSpeak" class="quick-action primary" type="button">
                <span class="quick-action-copy">
                  <strong>Play sample</strong>
                  <span id="quickSpeakDetail">Generates local Mac speech and plays it in the browser.</span>
                </span>
                <span class="quick-action-cue" aria-hidden="true">Press</span>
              </button>
            </div>
            <div class="flow-status" id="flowStatus">Ready: click "Play sample" to prove the loop works.</div>
          </section>
          <div id="samplePlayer" class="sample-player hidden">
            <div class="sample-player-label">Generated sample playback. Use this to replay, pause, or scrub the last sample.</div>
            <audio id="audio" controls></audio>
          </div>
        </div>
      </details>

      <details class="layer panel" data-section-key="voice">
        <summary>
          <span class="summary-copy">
            <span class="summary-kicker">Voice out</span>
            <span class="summary-title">Choose how responses should sound</span>
            <span class="summary-description">Switch providers, compare voices, and tune speed or model after the sample path works.</span>
          </span>
          <span class="summary-icon" aria-hidden="true">+</span>
        </summary>
        <div class="layer-body">
          <div class="control-group">
            <div class="segmented" aria-label="TTS provider">
              <button type="button" data-tts-provider="local" class="active">Local say</button>
              <button type="button" data-tts-provider="elevenlabs">ElevenLabs</button>
            </div>
            <div id="localTtsControls" class="split">
              <label>Voice
                <input id="localVoice" list="localVoices" autocomplete="off">
                <datalist id="localVoices"></datalist>
              </label>
              <label>Rate
                <input id="localRate" type="number" min="80" max="360" step="5">
              </label>
            </div>
            <div id="elevenTtsControls" class="split hidden">
              <label>Voice
                <input id="elevenlabsVoice" list="elevenlabsVoices" autocomplete="off">
                <datalist id="elevenlabsVoices"></datalist>
              </label>
              <label>TTS model
                <select id="elevenlabsTtsModel">
                  <option value="eleven_flash_v2_5">eleven_flash_v2_5</option>
                  <option value="eleven_turbo_v2_5">eleven_turbo_v2_5</option>
                  <option value="eleven_multilingual_v2">eleven_multilingual_v2</option>
                  <option value="eleven_v3">eleven_v3</option>
                </select>
              </label>
            </div>
            <label class="toggle">
              <input id="useMacSpeaker" type="checkbox">
              <span>Also play local TTS through the Mac speaker</span>
            </label>
            <div class="actions">
              <button id="loadVoices" type="button">Load voices</button>
              <button id="checkTts" type="button">Check TTS</button>
            </div>
            <div class="console-line" id="ttsCheckStatus">TTS check has not run yet.</div>
          </div>
        </div>
      </details>

      <details class="layer panel" data-section-key="listen">
        <summary>
          <span class="summary-copy">
            <span class="summary-kicker">Voice in</span>
            <span class="summary-title">Record or upload audio for transcription</span>
            <span class="summary-description">Use this layer when tuning how the skill listens. Browser recording stays separate from voice output settings.</span>
          </span>
          <span class="summary-icon" aria-hidden="true">+</span>
        </summary>
        <div class="layer-body">
          <div class="control-group">
            <div class="segmented" aria-label="STT provider">
              <button type="button" data-stt-provider="local" class="active">Local mlx</button>
              <button type="button" data-stt-provider="elevenlabs">ElevenLabs</button>
            </div>
            <div id="localSttControls">
              <label>Local STT model
                <input id="localSttModel" autocomplete="off">
              </label>
            </div>
            <div id="elevenSttControls" class="hidden">
              <label>ElevenLabs STT model
                <input id="elevenlabsSttModel" autocomplete="off">
              </label>
            </div>
            <label>Record seconds
              <input id="recordSeconds" type="number" min="1" max="60" step="1">
            </label>
            <div class="actions">
              <button id="checkStt" type="button">Check STT</button>
            </div>
            <div class="console-line" id="sttCheckStatus">STT check has not run yet.</div>
          </div>
          <div class="control-group">
            <div class="actions">
              <button id="record" type="button" class="warning">Record then transcribe</button>
              <button id="stopRecord" type="button" class="danger" disabled>Stop</button>
              <button id="transcribeRecording" type="button" disabled>Transcribe recording</button>
            </div>
            <div class="meter" aria-hidden="true"><span id="recordMeter"></span></div>
            <div class="console-line" id="recordStatus">Record captures the chosen duration, then transcribes automatically. Stop captures without transcribing.</div>
          </div>

          <div class="drop">
            <div>
              <strong>Transcribe an audio file</strong>
              <input id="audioFile" type="file" accept="audio/*">
            </div>
          </div>

          <label>Transcript
            <textarea id="transcript" readonly></textarea>
          </label>
        </div>
      </details>

      <details class="layer panel" data-section-key="save">
        <summary>
            <span class="summary-copy">
              <span class="summary-kicker">Keep it</span>
            <span class="summary-title">Save as skill defaults</span>
            <span class="summary-description">Apply provider, voice, model, rate, and listening choices to future vocal skill runs.</span>
          </span>
          <span class="summary-icon" aria-hidden="true">+</span>
        </summary>
        <div class="layer-body">
          <div class="save-explainer">
            <strong>Saving writes a local preferences file for this skill.</strong>
            <p>Most skills do not persist data. This console only saves when you press the button, then future vocal runs can start from these personal defaults.</p>
          </div>
          <div class="save-path">
            <span>Preference file</span>
            <code id="preferencesPath">Loading preference path...</code>
            <small>Local JSON only. The file is ignored by git and is not sent to ElevenLabs.</small>
          </div>
          <div class="settings-preview-panel">
            <div class="settings-preview-head">
              <h3>Current settings to save</h3>
              <span id="settingsSavedState">Loading saved state...</span>
            </div>
            <dl class="settings-preview" id="settingsPreview"></dl>
          </div>
          <div class="actions">
            <button id="savePrefs" class="primary" type="button">Save as skill defaults</button>
            <button id="speakSample" type="button">Speak current sample</button>
            <button id="stopAudio" type="button">Stop audio</button>
          </div>
          <div class="command-preview-block">
            <h3 class="preview-label">Command preview</h3>
            <pre id="commandPreview"></pre>
          </div>
          <div class="console-line" id="saveStatus"></div>
          <pre id="log"></pre>
        </div>
      </details>

      <details class="layer panel" data-section-key="guide">
        <summary>
          <span class="summary-copy">
            <span class="summary-kicker">Guide</span>
            <span class="summary-title">How to think about this console</span>
            <span class="summary-description">A short reference for the mental model behind TTS, STT, providers, and saved defaults.</span>
          </span>
          <span class="summary-icon" aria-hidden="true">+</span>
        </summary>
        <div class="layer-body">
          <div class="guide-grid">
            <div class="guide-note">
              <h3>Start with output</h3>
              <p>TTS is the fastest feedback loop. First prove the browser can generate and play speech, then tune voice, speed, and provider.</p>
            </div>
            <div class="guide-note">
              <h3>Local versus cloud</h3>
              <p>Local uses macOS voices and works without an account. ElevenLabs can sound better, but needs `ELEVENLABS_API_KEY` or `ELEVEN_LABS_API_KEY`.</p>
            </div>
            <div class="guide-note">
              <h3>Input is separate</h3>
              <p>STT controls are intentionally separate from TTS. Tune listening after speech output feels right.</p>
            </div>
            <div class="guide-note">
              <h3>Saving is personal</h3>
              <p>Saved defaults live in local skill data and are not committed. The command preview shows what the skill will do with your current choices.</p>
            </div>
          </div>
        </div>
      </details>
    </main>
  </div>

  <script>
    const defaultPrefs = JSON.parse(atob("__DEFAULT_PREFS_B64__"));
    let prefs = {...defaultPrefs};
    let mediaRecorder = null;
    let recordedBlob = null;
    let recordTimer = null;
    let recordStarted = 0;
    let recordStopMode = "manual";
    let runtimeStatus = {};
    let preferenceFilePath = "";
    let lastSavedSignature = "";
    let savedPrefs = null;

    const $ = (id) => document.getElementById(id);

    const fields = [
      "sampleText",
      "localVoice",
      "localRate",
      "useMacSpeaker",
      "elevenlabsVoice",
      "elevenlabsTtsModel",
      "localSttModel",
      "elevenlabsSttModel",
      "recordSeconds",
    ];

    const layerStoragePrefix = "vocal-console.layer.";

    function readStorage(key) {
      try {
        return window.localStorage.getItem(key);
      } catch {
        return null;
      }
    }

    function writeStorage(key, value) {
      try {
        window.localStorage.setItem(key, value);
      } catch {
        // Private browsing or restricted storage should not block the console.
      }
    }

    function restoreLayerState() {
      document.querySelectorAll("details[data-section-key]").forEach((layer) => {
        const key = `${layerStoragePrefix}${layer.dataset.sectionKey}`;
        const saved = readStorage(key);
        if (saved === "open") layer.open = true;
        if (saved === "closed") layer.open = false;
        layer.addEventListener("toggle", () => {
          writeStorage(key, layer.open ? "open" : "closed");
        });
      });
    }

    function setActivity(message) {
      const activity = $("activity");
      if (activity) activity.textContent = message;
    }

    function setFlow(message) {
      $("flowStatus").textContent = message;
    }

    function log(message) {
      const stamp = new Date().toLocaleTimeString();
      $("log").textContent = `[${stamp}] ${message}\n` + $("log").textContent;
    }

    function currentPrefs() {
      return {
        ttsProvider: prefs.ttsProvider,
        sttProvider: prefs.sttProvider,
        sampleText: $("sampleText").value,
        localVoice: $("localVoice").value,
        localRate: Number($("localRate").value || defaultPrefs.localRate),
        useMacSpeaker: $("useMacSpeaker").checked,
        elevenlabsVoice: $("elevenlabsVoice").value,
        elevenlabsTtsModel: $("elevenlabsTtsModel").value,
        localSttModel: $("localSttModel").value,
        elevenlabsSttModel: $("elevenlabsSttModel").value,
        recordSeconds: Number($("recordSeconds").value || defaultPrefs.recordSeconds),
      };
    }

    function applyPrefs(next) {
      prefs = {...defaultPrefs, ...next};
      for (const field of fields) {
        if ($(field).type === "checkbox") {
          $(field).checked = Boolean(prefs[field]);
        } else {
          $(field).value = prefs[field] ?? "";
        }
      }
      selectProvider("tts", prefs.ttsProvider);
      selectProvider("stt", prefs.sttProvider);
      applyProviderAvailability();
      updatePreview();
    }

    function selectProvider(kind, provider) {
      prefs[kind + "Provider"] = provider;
      if (provider === "elevenlabs" && runtimeStatus.hasElevenLabsKey === false) {
        setFlow("ElevenLabs is not configured in this shell. Use local say for the no-account path.");
      }
      document.querySelectorAll(`[data-${kind}-provider]`).forEach((button) => {
        button.classList.toggle("active", button.dataset[kind + "Provider"] === provider);
      });
      $("localTtsControls").classList.toggle("hidden", prefs.ttsProvider !== "local");
      $("elevenTtsControls").classList.toggle("hidden", prefs.ttsProvider !== "elevenlabs");
      $("localSttControls").classList.toggle("hidden", prefs.sttProvider !== "local");
      $("elevenSttControls").classList.toggle("hidden", prefs.sttProvider !== "elevenlabs");
      updateQuickProvider();
      updatePreview();
    }

    function applyProviderAvailability() {
      const option = $("quickTtsProvider").querySelector("option[value='elevenlabs']");
      if (runtimeStatus.hasElevenLabsKey === false) {
        option.disabled = true;
        option.textContent = "ElevenLabs (not set up)";
      } else {
        option.disabled = false;
        option.textContent = "ElevenLabs cloud";
      }
      if (runtimeStatus.hasElevenLabsKey === false && prefs.ttsProvider === "elevenlabs") {
        selectProvider("tts", "local");
        setFlow("ElevenLabs key not found. Local say is selected so the sample button works now.");
      }
      updateQuickProvider();
    }

    function updateQuickProvider() {
      const select = $("quickTtsProvider");
      if (!select) return;
      select.value = prefs.ttsProvider;
      $("quickProviderHint").textContent = prefs.ttsProvider === "elevenlabs"
        ? "Uses your ElevenLabs key for the sample."
        : "Local macOS speech. No account required.";
      $("quickSpeakDetail").textContent = prefs.ttsProvider === "elevenlabs"
        ? "Generates ElevenLabs audio and plays it in the browser."
        : "Generates local Mac speech and plays it in the browser.";
    }

    function shellQuote(value) {
      return "'" + String(value).replaceAll("'", "'\"'\"'") + "'";
    }

    function settingsSignature(state) {
      return JSON.stringify(state);
    }

    function providerName(provider) {
      return provider === "elevenlabs" ? "ElevenLabs" : "Local";
    }

    function shortText(value) {
      const compact = String(value || "").replace(/\s+/g, " ").trim();
      return compact.length > 110 ? compact.slice(0, 107) + "..." : compact;
    }

    function addSetting(list, label, value) {
      const term = document.createElement("dt");
      const description = document.createElement("dd");
      term.textContent = label;
      description.textContent = value;
      list.append(term, description);
    }

    function settingRows(state) {
      return [
        ["Speech provider", providerName(state.ttsProvider)],
        [
          "Speech voice",
          state.ttsProvider === "elevenlabs"
            ? `${state.elevenlabsVoice} / ${state.elevenlabsTtsModel}`
            : `${state.localVoice} / ${state.localRate} wpm`,
        ],
        ["Listening provider", providerName(state.sttProvider)],
        [
          "Listening model",
          state.sttProvider === "elevenlabs" ? state.elevenlabsSttModel : state.localSttModel,
        ],
        ["Record length", `${state.recordSeconds}s`],
        ["Mac speaker", state.useMacSpeaker ? "Also play local TTS through the Mac speaker" : "Browser playback only"],
        ["Sample text", shortText(state.sampleText)],
      ];
    }

    function renderSettingsList(list, rows) {
      list.replaceChildren();
      rows.forEach(([label, value]) => addSetting(list, label, value));
    }

    function addDefaultPreviewItem(list, label, value) {
      const group = document.createElement("div");
      const term = document.createElement("dt");
      const description = document.createElement("dd");
      term.textContent = label;
      description.textContent = value;
      group.append(term, description);
      list.append(group);
    }

    function savedSummaryRows(state) {
      return [
        [
          "Speech",
          state.ttsProvider === "elevenlabs"
            ? `ElevenLabs / ${state.elevenlabsVoice}`
            : `Local / ${state.localVoice} / ${state.localRate} wpm`,
        ],
        [
          "Listening",
          state.sttProvider === "elevenlabs"
            ? `ElevenLabs / ${state.elevenlabsSttModel}`
            : `Local / ${state.localSttModel}`,
        ],
        ["Recording", `${state.recordSeconds}s / ${state.useMacSpeaker ? "Mac speaker also on" : "browser playback only"}`],
        ["Sample", shortText(state.sampleText)],
      ];
    }

    function updateDefaultsOverview(state) {
      const path = preferenceFilePath || "loading...";
      const savedState = savedPrefs || state;
      $("defaultsPath").textContent = `Preference file: ${path}`;
      $("defaultsSavedState").textContent = lastSavedSignature && settingsSignature(state) === lastSavedSignature
        ? "Current controls match saved defaults"
        : "Unsaved changes in the controls below";
      $("defaultsHelp").textContent = lastSavedSignature && settingsSignature(state) === lastSavedSignature
        ? "Change a provider, voice, model, duration, or sample below to try a new default."
        : "Preview the changed values, then open Save as skill defaults when you want them to persist.";

      const list = $("defaultsPreview");
      list.replaceChildren();
      savedSummaryRows(savedState).forEach(([label, value]) => addDefaultPreviewItem(list, label, value));
    }

    function updateSaveSummary(state) {
      const path = preferenceFilePath || "Preference path will appear after the console loads.";
      $("preferencesPath").textContent = path;
      $("settingsSavedState").textContent = lastSavedSignature && settingsSignature(state) === lastSavedSignature
        ? "Matches saved file"
        : "Unsaved changes";

      renderSettingsList($("settingsPreview"), settingRows(state));
      updateDefaultsOverview(state);
    }

    function updatePreview() {
      const state = currentPrefs();
      const ttsScript = state.ttsProvider === "local" ? "tts_local.py" : "tts_elevenlabs.py";
      const sttScript = state.sttProvider === "local" ? "stt_local.py" : "stt_elevenlabs.py";
      const ttsArgs = state.ttsProvider === "local"
        ? `--voice ${shellQuote(state.localVoice)} --rate ${state.localRate}`
        : `--voice ${shellQuote(state.elevenlabsVoice)} --model ${shellQuote(state.elevenlabsTtsModel)}`;
      const sttArgs = state.sttProvider === "local"
        ? `--model ${shellQuote(state.localSttModel)}`
        : `--model ${shellQuote(state.elevenlabsSttModel)}`;
      $("commandPreview").textContent =
        `uv run --script ~/.claude/skills/vocal/scripts/web_console.py --port 8765\n\n` +
        `uv run --script ~/.claude/skills/vocal/scripts/${ttsScript} --text ${shellQuote(state.sampleText)} ${ttsArgs}\n` +
        `uv run --script ~/.claude/skills/vocal/scripts/${sttScript} --duration ${state.recordSeconds} ${sttArgs}\n\n` +
        `/vocal stt=${state.sttProvider} tts=${state.ttsProvider} duration=${state.recordSeconds} ${state.sampleText}`;
      updateSaveSummary(state);
    }

    async function fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || data.stderr || data.stdout || response.statusText);
      }
      return data;
    }

    async function loadStatus() {
      const status = await fetchJson("/api/status");
      runtimeStatus = status;
      const items = [
        {
          key: "elevenlabs",
          label: status.hasElevenLabsKey ? "ElevenLabs ready" : "ElevenLabs not set",
          ok: status.hasElevenLabsKey,
          tooltip: status.hasElevenLabsKey
            ? "Cloud voices and transcription can use your ElevenLabs key."
            : "Set ELEVENLABS_API_KEY or ELEVEN_LABS_API_KEY in .env to enable cloud voice.",
        },
        {
          key: "say",
          label: status.hasSay ? "Local speech ready" : "Local speech missing",
          ok: status.hasSay,
          tooltip: "macOS say powers the no-account Hear the sample flow.",
        },
        {
          key: "afplay",
          label: status.hasAfplay ? "Mac playback ready" : "Mac playback missing",
          ok: status.hasAfplay,
          tooltip: "afplay lets local generated audio play through the Mac speaker when enabled.",
        },
        {
          key: "uv",
          label: status.hasUv ? "uv runner ready" : "uv runner missing",
          ok: status.hasUv,
          tooltip: "uv runs the vocal skill scripts from this web console.",
        },
      ];
      $("statusStrip").innerHTML = items.map((item) => {
        const classes = ["status-check", item.ok ? "good" : "bad"].join(" ");
        return `<span class="${classes}" data-status="${item.key}" data-tooltip="${item.tooltip}" title="${item.tooltip}" tabindex="0" aria-label="${item.label}. ${item.tooltip}">${item.label}</span>`;
      }).join("");
      $("statusStrip").insertAdjacentHTML("afterbegin", '<span class="status-label">Setup</span>');
      applyProviderAvailability();
    }

    async function loadPrefs() {
      const data = await fetchJson("/api/preferences");
      preferenceFilePath = data.path;
      applyPrefs(data.preferences);
      savedPrefs = {...currentPrefs()};
      lastSavedSignature = settingsSignature(currentPrefs());
      updateSaveSummary(currentPrefs());
      $("saveStatus").textContent = `Loaded saved defaults from ${data.path}`;
    }

    async function savePrefs() {
      setActivity("saving");
      const data = await fetchJson("/api/preferences", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify(currentPrefs()),
      });
      preferenceFilePath = data.path;
      applyPrefs(data.preferences);
      savedPrefs = {...currentPrefs()};
      lastSavedSignature = settingsSignature(currentPrefs());
      updateSaveSummary(currentPrefs());
      $("saveStatus").textContent = `Saved defaults to ${data.path}`;
      setActivity("ready");
      setFlow("Saved. These defaults will load the next time you open the console.");
      log("Saved preferences.");
    }

    async function loadVoices() {
      const provider = prefs.ttsProvider;
      setActivity(`loading ${provider} voices`);
      const data = await fetchJson(`/api/voices?provider=${encodeURIComponent(provider)}`);
      const list = provider === "local" ? $("localVoices") : $("elevenlabsVoices");
      list.innerHTML = "";
      for (const voice of data.voices) {
        const option = document.createElement("option");
        option.value = voice.name;
        option.label = voice.detail;
        list.appendChild(option);
      }
      setActivity("ready");
      setFlow(`Loaded ${data.voices.length} voices. Pick one, then click "Hear the sample" again.`);
      log(`Loaded ${data.voices.length} ${provider} voices.`);
    }

    async function check(kind) {
      const state = currentPrefs();
      const provider = kind === "tts" ? state.ttsProvider : state.sttProvider;
      const model = provider === "local" ? state.localSttModel : state.elevenlabsSttModel;
      const statusLine = kind === "tts" ? $("ttsCheckStatus") : $("sttCheckStatus");
      setActivity(`checking ${kind}`);
      statusLine.textContent = `Checking ${kind.toUpperCase()} with ${provider}...`;
      const data = await fetchJson("/api/check", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({kind, provider, model}),
      });
      setActivity("ready");
      statusLine.textContent = `${kind.toUpperCase()} ${data.ok ? "ready" : "needs attention"}: ${data.stdout || data.stderr || "check completed"}`;
      setFlow(`${kind.toUpperCase()} check finished: ${data.ok ? "ready" : "needs attention"}.`);
      log(`${kind}/${provider}: ${data.ok ? "OK" : "FAIL"} ${data.stdout || data.stderr}`);
    }

    function handleCheckError(kind, err) {
      const statusLine = kind === "tts" ? $("ttsCheckStatus") : $("sttCheckStatus");
      setActivity("ready");
      statusLine.textContent = `${kind.toUpperCase()} check failed: ${err.message}`;
      setFlow(`${kind.toUpperCase()} check failed. See the status in its layer.`);
      log(err.message);
    }

    async function waitForAudioReady() {
      const audio = $("audio");
      await new Promise((resolve, reject) => {
        const started = Date.now();
        const timer = setInterval(() => {
          if (Number.isFinite(audio.duration) && audio.duration > 0) {
            clearInterval(timer);
            resolve();
          } else if (Date.now() - started > 8000) {
            clearInterval(timer);
            reject(new Error("Audio was generated, but the browser could not read its duration."));
          }
        }, 100);
      });
    }

    async function speakSample() {
      const state = currentPrefs();
      const body = {
        provider: state.ttsProvider,
        text: state.sampleText,
        useMacSpeaker: state.useMacSpeaker,
        voice: state.ttsProvider === "local" ? state.localVoice : state.elevenlabsVoice,
        rate: state.localRate,
        model: state.elevenlabsTtsModel,
      };
      setActivity("speaking");
      setFlow("Generating a browser-playable sample...");
      const response = await fetch("/api/synthesize", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "TTS request failed");
      }
      const blob = await response.blob();
      $("audio").src = URL.createObjectURL(blob);
      $("audio").load();
      await waitForAudioReady();
      $("samplePlayer").classList.remove("hidden");
      setActivity("ready");
      setFlow(`Sample ready: ${Math.round($("audio").duration * 10) / 10}s of audio in the player.`);
      $("audio").play().catch(() => {});
      log(`Generated ${Math.round(blob.size / 1024)} KB audio sample.`);
    }

    async function startRecording() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("This browser cannot access microphone recording from this page.");
      }
      $("recordStatus").textContent = "Requesting microphone permission...";
      const stream = await navigator.mediaDevices.getUserMedia({audio: true});
      recordedBlob = null;
      const chunks = [];
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        recordedBlob = new Blob(chunks, {type: mediaRecorder.mimeType || "audio/webm"});
        const size = Math.round(recordedBlob.size / 1024);
        const shouldAutoTranscribe = recordStopMode === "auto";
        recordStopMode = "manual";
        $("recordStatus").textContent = shouldAutoTranscribe
          ? `Recorded ${size} KB. Transcribing automatically...`
          : `Stopped. Recorded ${size} KB. Click "Transcribe recording" when ready.`;
        setFlow(shouldAutoTranscribe ? "Recording captured. Transcribing automatically..." : 'Recording stopped. Click "Transcribe recording" if you want a transcript.');
        $("transcribeRecording").disabled = false;
        $("recordMeter").style.width = "0%";
        if (shouldAutoTranscribe) {
          $("transcribeRecording").disabled = true;
          transcribeBlob(recordedBlob, "browser-recording.webm")
            .then(() => {
              $("recordStatus").textContent = `Recorded ${size} KB. Transcript ready below.`;
              $("transcribeRecording").disabled = false;
            })
            .catch((err) => {
              $("recordStatus").textContent = `Recorded ${size} KB. Auto transcription failed: ${err.message}`;
              $("transcribeRecording").disabled = false;
              log(err.message);
            });
        }
      };
      mediaRecorder.start();
      recordStarted = Date.now();
      $("record").disabled = true;
      $("stopRecord").disabled = false;
      $("recordStatus").textContent = `Recording for up to ${$("recordSeconds").value || 5}s. Will transcribe automatically when time is up.`;
      const limit = Number($("recordSeconds").value || 5);
      recordTimer = setInterval(() => {
        const elapsed = (Date.now() - recordStarted) / 1000;
        $("recordMeter").style.width = `${Math.min(100, (elapsed / limit) * 100)}%`;
        if (elapsed >= limit) stopRecording({autoTranscribe: true});
      }, 100);
    }

    function stopRecording({autoTranscribe = false} = {}) {
      clearInterval(recordTimer);
      recordTimer = null;
      recordStopMode = autoTranscribe ? "auto" : "manual";
      if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
      $("record").disabled = false;
      $("stopRecord").disabled = true;
    }

    function handleRecordError(err) {
      $("record").disabled = false;
      $("stopRecord").disabled = true;
      $("transcribeRecording").disabled = true;
      $("recordMeter").style.width = "0%";
      $("recordStatus").textContent = `Microphone unavailable: ${err.message}`;
      log(err.message);
    }

    async function transcribeBlob(blob, filename) {
      const state = currentPrefs();
      const form = new FormData();
      form.append("audio", blob, filename);
      form.append("payload", JSON.stringify({
        provider: state.sttProvider,
        model: state.sttProvider === "local" ? state.localSttModel : state.elevenlabsSttModel,
        contentType: blob.type,
      }));
      setActivity("transcribing");
      setFlow("Transcribing the selected audio...");
      const data = await fetchJson("/api/transcribe", {method: "POST", body: form});
      $("transcript").value = data.transcript || "";
      setActivity("ready");
      setFlow(data.transcript ? "Transcript ready." : "Transcription finished without text. Check the log.");
      log(`STT ${data.ok ? "OK" : "FAIL"} ${data.transcript || data.stderr || data.stdout}`);
    }

    function bind() {
      document.querySelectorAll("[data-tts-provider]").forEach((button) => {
        button.addEventListener("click", () => selectProvider("tts", button.dataset.ttsProvider));
      });
      document.querySelectorAll("[data-stt-provider]").forEach((button) => {
        button.addEventListener("click", () => selectProvider("stt", button.dataset.sttProvider));
      });
      fields.forEach((field) => $(field).addEventListener("input", updatePreview));
      fields.forEach((field) => $(field).addEventListener("change", updatePreview));
      $("quickTtsProvider").addEventListener("change", () => {
        selectProvider("tts", $("quickTtsProvider").value);
        setFlow(`Using ${prefs.ttsProvider === "elevenlabs" ? "ElevenLabs" : "local macOS speech"}. Click "Hear the sample" to listen.`);
      });
      $("savePrefs").addEventListener("click", () => savePrefs().catch((err) => log(err.message)));
      $("quickSpeak").addEventListener("click", () => {
        speakSample().catch((err) => { setActivity("ready"); setFlow(err.message); log(err.message); });
      });
      $("loadVoices").addEventListener("click", () => loadVoices().catch((err) => log(err.message)));
      $("checkTts").addEventListener("click", () => check("tts").catch((err) => handleCheckError("tts", err)));
      $("checkStt").addEventListener("click", () => check("stt").catch((err) => handleCheckError("stt", err)));
      $("speakSample").addEventListener("click", () => speakSample().catch((err) => { setActivity("ready"); setFlow(err.message); log(err.message); }));
      $("stopAudio").addEventListener("click", () => { $("audio").pause(); $("audio").currentTime = 0; });
      $("record").addEventListener("click", () => startRecording().catch(handleRecordError));
      $("stopRecord").addEventListener("click", () => stopRecording());
      $("transcribeRecording").addEventListener("click", () => {
        if (recordedBlob) transcribeBlob(recordedBlob, "browser-recording.webm").catch((err) => log(err.message));
      });
      $("reviewSaveDefaults").addEventListener("click", () => {
        const saveLayer = document.querySelector("[data-section-key='save']");
        saveLayer.open = true;
        saveLayer.scrollIntoView({behavior: "smooth", block: "start"});
      });
      $("audioFile").addEventListener("change", (event) => {
        const file = event.target.files[0];
        if (file) transcribeBlob(file, file.name).catch((err) => log(err.message));
      });
    }

    bind();
    restoreLayerState();
    applyPrefs(defaultPrefs);
    (async function init() {
      await loadStatus();
      await loadPrefs();
      applyProviderAvailability();
    })().catch((err) => log(err.message));
  </script>
</body>
</html>
"""


def serve(host: str, port: int, open_browser: bool) -> None:
    load_dotenv()
    data_dir = data_dir_from_env()
    handler = make_handler(data_dir)
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{server.server_port}"
    print(f"Vocal web console: {url}", flush=True)
    print(f"Preferences: {preferences_path(data_dir)}", flush=True)
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down vocal web console.")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Host the vocal skill web tuning console")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765, 0 for any free port)")
    parser.add_argument("--open", action="store_true", help="Open the console in the default browser")
    args = parser.parse_args()
    serve(args.host, args.port, args.open)


if __name__ == "__main__":
    main()
