"""Shared helpers for the image-gen provider scripts."""

from __future__ import annotations

import os
import hashlib
import json
import shlex
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

OUTPUT_FORMAT_TO_EXT = {
    "jpeg": ".jpg",
    "jpg": ".jpg",
    "png": ".png",
    "webp": ".webp",
}

EXT_TO_OUTPUT_FORMAT = {
    ".jpeg": "jpeg",
    ".jpg": "jpeg",
    ".png": "png",
    ".webp": "webp",
}

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = SKILL_DIR / "outputs"
DEFAULT_DATA_DIR = SKILL_DIR / "data"


def error_exit(msg: str, hint: str | None = None) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    if hint:
        print(f"\n{hint}", file=sys.stderr)
    sys.exit(1)


def load_dotenv_files() -> None:
    """Load simple KEY=VALUE lines from .env files without overriding the shell."""

    for path in (Path.cwd() / ".env", Path.home() / ".env"):
        if not path.exists():
            continue
        try:
            load_dotenv_file(path)
        except OSError:
            continue


def load_dotenv_file(path: Path) -> None:
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        value = value.strip()
        if value:
            try:
                parsed = shlex.split(value, comments=True, posix=True)
                value = parsed[0] if parsed else ""
            except ValueError:
                value = value.strip("'\"")
        os.environ[key] = value


def get_env_var(names: tuple[str, ...], hint_url: str) -> str:
    load_dotenv_files()
    for name in names:
        api_key = os.environ.get(name)
        if api_key:
            return api_key

    display_names = " or ".join(names)
    dotenv_line = f"{names[0]}=your-key-here"
    error_exit(
        f"{display_names} environment variable not set",
        "To fix, either:\n"
        f"  1. Add to ~/.env:      {dotenv_line}\n"
        f"  2. Or export in shell: export {dotenv_line}\n\n"
        f"Get your API key at: {hint_url}",
    )


def default_output_dir(output_dir: Path | None = None) -> Path:
    if output_dir is not None:
        return output_dir.expanduser()

    configured = os.environ.get("IMAGE_GEN_OUTPUT_DIR")
    if configured:
        return Path(configured).expanduser()

    return DEFAULT_OUTPUT_DIR


def default_data_dir(data_dir: Path | None = None) -> Path:
    if data_dir is not None:
        return data_dir.expanduser()

    configured = os.environ.get("IMAGE_GEN_DATA_DIR")
    if configured:
        return Path(configured).expanduser()

    return DEFAULT_DATA_DIR


def timestamped_output(
    default_ext: str,
    output_dir: Path | None = None,
    prefix: str = "generated",
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return default_output_dir(output_dir) / f"{prefix}-{timestamp}{default_ext}"


def output_format_from_path(output: Path | None, default: str) -> str:
    if output and output.suffix.lower() in EXT_TO_OUTPUT_FORMAT:
        return EXT_TO_OUTPUT_FORMAT[output.suffix.lower()]
    return default


def normalize_output_path(
    output: Path | None,
    expected_ext: str,
    output_dir: Path | None = None,
    prefix: str = "generated",
) -> Path:
    path = output or timestamped_output(expected_ext, output_dir, prefix)
    current_ext = path.suffix.lower()
    equivalent_exts = {expected_ext}
    if expected_ext == ".jpg":
        equivalent_exts.add(".jpeg")
    if current_ext and current_ext not in equivalent_exts:
        corrected = path.with_suffix(expected_ext)
        print(
            f"Note: saving as {corrected.name} instead of {path.name} "
            "to match the generated format",
            file=sys.stderr,
        )
        path = corrected
    return path


def write_output(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def history_enabled() -> bool:
    disabled = os.environ.get("IMAGE_GEN_DISABLE_HISTORY", "").strip().lower()
    return disabled not in {"1", "true", "yes", "on"}


def image_dimensions(path: Path) -> dict[str, int] | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None

    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return {"width": width, "height": height}

    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            while index < len(data) and data[index] == 0xFF:
                index += 1
            if index >= len(data):
                return None
            marker = data[index]
            index += 1
            if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
                continue
            if index + 2 > len(data):
                return None
            segment_length = int.from_bytes(data[index : index + 2], "big")
            if segment_length < 2 or index + segment_length > len(data):
                return None
            if marker in {
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            }:
                height = int.from_bytes(data[index + 3 : index + 5], "big")
                width = int.from_bytes(data[index + 5 : index + 7], "big")
                return {"width": width, "height": height}
            index += segment_length

    return None


def record_generation(
    *,
    provider: str,
    model: str,
    prompt: str,
    output_path: Path,
    parameters: dict[str, Any],
    data_dir: Path | None = None,
) -> None:
    if not history_enabled():
        return

    try:
        resolved_output = output_path.resolve()
        dimensions = image_dimensions(output_path)
        entry = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "model": model,
            "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "output_path": str(resolved_output),
            "output_path_relative_to_skill": relative_to_skill(resolved_output),
            "output_size_bytes": output_path.stat().st_size,
            "output_suffix": output_path.suffix.lower(),
            "dimensions": dimensions,
            "parameters": compact_parameters(parameters),
        }

        history_path = default_data_dir(data_dir) / "generations.jsonl"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry, sort_keys=True) + "\n")
    except OSError:
        return


def relative_to_skill(path: Path) -> str | None:
    try:
        return str(path.relative_to(SKILL_DIR))
    except ValueError:
        return None


def compact_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in parameters.items() if value is not None}


def ext_for_mime(mime_type: str | None, default: str = ".jpg") -> str:
    if not mime_type:
        return default
    return MIME_TO_EXT.get(mime_type.split(";")[0].strip().lower(), default)
