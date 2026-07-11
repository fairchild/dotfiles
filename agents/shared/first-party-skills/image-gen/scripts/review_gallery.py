#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Serve an interactive review UI for image-gen comparison runs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import shutil
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from common import SKILL_DIR, default_data_dir, image_dimensions


SCRIPTS_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SKILL_DIR / "assets" / "review-gallery.html"
PROVIDER_SCRIPTS = {
    "openai": "generate_openai.py",
    "gemini": "generate_gemini.py",
    "imagen": "generate_imagen.py",
    "fal": "generate_fal.py",
}
REGEN_SUFFIX_RE = re.compile(r"__regen-\d{8}-\d{6}$")


class ReviewState:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir.resolve()
        self.manifest_path = self.run_dir / "manifest.json"
        self.feedback_path = self.run_dir / "feedback.json"
        self.lock = threading.Lock()

    def manifest(self) -> dict:
        return json.loads(self.manifest_path.read_text())

    def save_manifest(self, manifest: dict) -> None:
        self.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    def feedback(self) -> dict | None:
        if not self.feedback_path.exists():
            return None
        return json.loads(self.feedback_path.read_text())

    def response_state(self) -> dict:
        manifest = self.manifest()
        feedback = self.feedback()
        outputs = manifest.get("outputs", [])
        for output in outputs:
            output["candidate_id"] = candidate_identity(output)
            path = self.run_dir / output["path"]
            output["cache_bust"] = str(path.stat().st_mtime_ns) if path.exists() else ""
            output["dimensions"] = image_dimensions(path) if path.exists() else None
        return {
            "id": manifest.get("id", self.run_dir.name),
            "prompt": manifest.get("prompt", ""),
            "outputs": outputs,
            "feedback": feedback,
        }

    def safe_path(self, relative_path: str) -> Path:
        path = (self.run_dir / relative_path).resolve()
        if not path.is_relative_to(self.run_dir):
            raise ValueError("path escapes run directory")
        return path

    def save_feedback(self, payload: dict) -> dict:
        with self.lock:
            manifest = self.manifest()
            outputs = manifest.get("outputs", [])
            winner_path = payload.get("winner_path")
            ranking = payload.get("ranking") or []
            comment = payload.get("comment", payload.get("comments", ""))
            if not winner_path:
                raise ValueError("winner_path is required")
            winner_matches = find_candidates(outputs, payload | {"path": winner_path})
            if winner_matches:
                winner_path = winner_matches[0]["path"]
            ranking = normalize_ranking(ranking, outputs)
            if not ranking or ranking[0] != winner_path:
                ranking = [winner_path, *[path for path in ranking if path != winner_path]]
            winner_file = self.safe_path(winner_path)
            if not winner_file.exists():
                raise ValueError(f"winner does not exist: {winner_path}")

            winner_copy = self.run_dir / f"winner{winner_file.suffix.lower()}"
            shutil.copy2(winner_file, winner_copy)
            feedback = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "run_id": manifest.get("id", self.run_dir.name),
                "prompt": manifest.get("prompt", ""),
                "winner_path": winner_path,
                "winner_copy": winner_copy.name,
                "ranking": ranking,
                "comment": comment,
                "outputs": outputs,
            }
            self.feedback_path.write_text(json.dumps(feedback, indent=2, sort_keys=True) + "\n")
            append_jsonl(default_data_dir() / "rankings.jsonl", feedback)
            return {
                "ok": True,
                "winner_path": str(winner_file),
                "winner_copy": str(winner_copy),
            }

    def regenerate(self, payload: dict, timeout: int) -> dict:
        with self.lock:
            manifest = self.manifest()
            outputs = manifest.get("outputs", [])
            if payload.get("all"):
                selected = outputs
            else:
                selected = find_candidates(outputs, payload)
            if not selected:
                raise ValueError("no matching candidates to regenerate")

            events = []
            for output in selected:
                event = self.regenerate_one(manifest, output, timeout)
                events.append(event)

            manifest.setdefault("regenerations", []).extend(events)
            self.save_manifest(manifest)
            return self.response_state()

    def regenerate_one(self, manifest: dict, output: dict, timeout: int) -> dict:
        old_path = output["path"]
        old_file = self.safe_path(old_path)
        suffix = old_file.suffix or ".png"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        new_name = f"{old_file.stem}__regen-{stamp}{suffix}"
        new_rel = str(Path(old_path).parent / new_name)
        new_file = self.run_dir / new_rel
        command = build_regenerate_command(
            provider=output["provider"],
            model=output["model"],
            prompt=manifest["prompt"],
            output_path=new_file,
            previous_path=old_file,
        )

        started = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        duration = round(time.monotonic() - started, 2)
        event = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provider": output["provider"],
            "model": output["model"],
            "old_path": old_path,
            "new_path": new_rel,
            "returncode": result.returncode,
            "duration_seconds": duration,
            "stderr": result.stderr,
        }
        append_jsonl(default_data_dir() / "regenerations.jsonl", event)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "regeneration failed")
        output["path"] = new_rel
        return event


def candidate_identity(output: dict) -> str:
    existing = output.get("candidate_id") or output.get("id")
    if existing:
        return str(existing)
    provider = output.get("provider", "unknown")
    model = output.get("model", "unknown")
    return f"{provider}:{model}"


def candidate_lineage_key(path: str) -> str:
    candidate_path = Path(path)
    stem = candidate_path.stem
    while True:
        next_stem = REGEN_SUFFIX_RE.sub("", stem)
        if next_stem == stem:
            break
        stem = next_stem
    return str(candidate_path.with_name(stem))


def find_candidates(outputs: list[dict], payload: dict) -> list[dict]:
    target_path = payload.get("path")
    if target_path:
        exact = [item for item in outputs if item.get("path") == target_path]
        if exact:
            return exact

    target_id = payload.get("candidate_id") or payload.get("id")
    if target_id:
        by_id = [item for item in outputs if candidate_identity(item) == target_id]
        if by_id:
            return by_id

    provider = payload.get("provider")
    model = payload.get("model")
    if provider and model:
        by_provider_model = [
            item
            for item in outputs
            if item.get("provider") == provider and item.get("model") == model
        ]
        if by_provider_model:
            return by_provider_model

    if target_path:
        target_lineage = candidate_lineage_key(target_path)
        by_lineage = [
            item
            for item in outputs
            if candidate_lineage_key(str(item.get("path", ""))) == target_lineage
        ]
        if by_lineage:
            return by_lineage

    return []


def normalize_ranking(ranking: list[str], outputs: list[dict]) -> list[str]:
    normalized = []
    for path in ranking:
        matches = find_candidates(outputs, {"path": path})
        if matches:
            current_path = matches[0]["path"]
            if current_path not in normalized:
                normalized.append(current_path)
    for output in outputs:
        path = output.get("path")
        if path and path not in normalized:
            normalized.append(path)
    return normalized


def append_jsonl(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, sort_keys=True) + "\n")


def build_regenerate_command(
    *,
    provider: str,
    model: str,
    prompt: str,
    output_path: Path,
    previous_path: Path,
) -> list[str]:
    script = PROVIDER_SCRIPTS.get(provider)
    if not script:
        raise ValueError(f"unsupported provider: {provider}")

    command = [
        str(SCRIPTS_DIR / script),
        "--model",
        model,
        "--prompt",
        prompt,
        "--output",
        str(output_path),
    ]
    command.extend(provider_args(provider, previous_path))
    return command


def provider_args(provider: str, previous_path: Path) -> list[str]:
    dimensions = image_dimensions(previous_path) or {"width": 1, "height": 1}
    width = dimensions["width"]
    height = dimensions["height"]
    output_format = "png" if previous_path.suffix.lower() == ".png" else "jpeg"

    if provider == "openai":
        if width > height * 1.2:
            size = "1536x1024"
        elif height > width * 1.2:
            size = "1024x1536"
        else:
            size = "1024x1024"
        return ["--size", size, "--output-format", output_format]

    if provider == "gemini":
        return ["--aspect-ratio", aspect_ratio(width, height), "--image-size", "1K"]

    if provider == "imagen":
        return ["--aspect-ratio", imagen_aspect_ratio(width, height), "--output-format", output_format]

    if provider == "fal":
        if width > height * 1.2:
            image_size = "landscape_16_9"
        elif height > width * 1.2:
            image_size = "portrait_16_9"
        else:
            image_size = "square"
        return ["--image-size", image_size, "--output-format", output_format]

    return []


def aspect_ratio(width: int, height: int) -> str:
    ratio = width / max(height, 1)
    if 0.9 <= ratio <= 1.1:
        return "1:1"
    if ratio >= 1.5:
        return "16:9"
    if ratio <= 0.7:
        return "9:16"
    if ratio > 1:
        return "4:3"
    return "3:4"


def imagen_aspect_ratio(width: int, height: int) -> str:
    ratio = aspect_ratio(width, height)
    return ratio if ratio in {"1:1", "3:4", "4:3", "9:16", "16:9"} else "1:1"


class ReviewHandler(BaseHTTPRequestHandler):
    server_version = "ImageGenReview/1.0"

    @property
    def review_state(self) -> ReviewState:
        return self.server.review_state  # type: ignore[attr-defined]

    @property
    def timeout_seconds(self) -> int:
        return self.server.timeout_seconds  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                self.send_html(TEMPLATE_PATH.read_text())
            elif parsed.path == "/api/state":
                self.send_json(self.review_state.response_state())
            elif parsed.path.startswith("/file/"):
                rel = unquote(parsed.path.removeprefix("/file/"))
                self.send_file(self.review_state.safe_path(rel))
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            self.send_json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self.read_json()
            if parsed.path == "/api/feedback":
                self.send_json(self.review_state.save_feedback(payload))
            elif parsed.path == "/api/regenerate":
                self.send_json(self.review_state.regenerate(payload, self.timeout_seconds))
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            self.send_json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def read_json(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, path: Path) -> None:
        if not path.exists():
            self.send_json({"error": "file not found"}, HTTPStatus.NOT_FOUND)
            return
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", mime_type)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def available_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError("no available port")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review and rank image-gen comparison outputs")
    parser.add_argument("--run-dir", type=Path, required=True, help="Comparison run directory")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8765, help="Preferred port")
    parser.add_argument("--timeout", type=int, default=300, help="Seconds per regeneration")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    if not (run_dir / "manifest.json").exists():
        parser.error(f"missing manifest.json in {run_dir}")

    port = available_port(args.host, args.port)
    server = ReusableThreadingHTTPServer((args.host, port), ReviewHandler)
    server.review_state = ReviewState(run_dir)  # type: ignore[attr-defined]
    server.timeout_seconds = args.timeout  # type: ignore[attr-defined]
    url = f"http://{args.host}:{port}/"
    print(url, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
