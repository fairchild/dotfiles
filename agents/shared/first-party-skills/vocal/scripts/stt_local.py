#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["mlx-whisper", "sounddevice", "numpy"]
# ///
"""Transcribe speech locally with mlx-whisper."""

import argparse
import platform
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd


def error_exit(msg: str, hint: str | None = None) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    if hint:
        print(f"\n{hint}", file=sys.stderr)
    sys.exit(1)


def ensure_apple_silicon() -> None:
    if platform.system() != "Darwin" or platform.machine() not in {"arm64", "aarch64"}:
        error_exit(
            "mlx-whisper local mode requires Apple Silicon macOS",
            "Use ElevenLabs cloud STT or run this on an Apple Silicon Mac.",
        )


def list_input_devices() -> list[tuple[int, str, int]]:
    devices = []
    for index, device in enumerate(sd.query_devices()):
        max_inputs = int(device["max_input_channels"])
        if max_inputs > 0:
            devices.append((index, str(device["name"]), max_inputs))
    return devices


def resolve_device(device: str | None) -> int | None:
    if device is None:
        return None

    try:
        return int(device)
    except ValueError:
        pass

    lowered = device.lower()
    matches = [index for index, name, _ in list_input_devices() if lowered in name.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        error_exit(
            f"Device name is ambiguous: {device}",
            "Use --list-devices and pass a numeric device index.",
        )
    error_exit(
        f"Input device not found: {device}",
        "Use --list-devices to see available microphones.",
    )
    raise AssertionError("unreachable")


def print_input_devices() -> None:
    devices = list_input_devices()
    if not devices:
        error_exit("No input devices found")
    for index, name, channels in devices:
        print(f"{index}\t{name}\tchannels={channels}")


def write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def ensure_audio_signal(audio: np.ndarray) -> None:
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if rms < 1e-6 and peak < 1e-5:
        error_exit(
            "Captured audio is silent (all zeros)",
            "Microphone audio is not reaching this process. Check app microphone permissions and selected input device.",
        )


def record_audio(duration: float, sample_rate: int = 16000, device: int | None = None) -> Path:
    if duration <= 0:
        error_exit("--duration must be greater than 0")

    frames = int(duration * sample_rate)
    try:
        audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32", device=device)
        sd.wait()
    except Exception as exc:
        error_exit(
            f"Unable to access microphone: {exc}",
            "Grant microphone access in System Settings -> Privacy & Security -> Microphone.",
        )

    mono = np.squeeze(audio)
    ensure_audio_signal(mono)
    temp = tempfile.NamedTemporaryFile(prefix="voice-stt-local-", suffix=".wav", delete=False)
    temp_path = Path(temp.name)
    temp.close()
    write_wav(temp_path, mono, sample_rate)
    return temp_path


def transcribe(audio_path: Path, model: str) -> str:
    import mlx_whisper

    try:
        result: Any = mlx_whisper.transcribe(str(audio_path), path_or_hf_repo=model)
    except Exception as exc:
        error_exit(
            f"mlx-whisper transcription failed: {exc}",
            "The first run may download model weights. Check network connectivity and disk space.",
        )

    text = str(result.get("text", "")).strip() if isinstance(result, dict) else str(result).strip()
    return text


def check_config(model: str, device: int | None) -> None:
    ensure_apple_silicon()

    try:
        sd.check_input_settings(samplerate=16000, channels=1, device=device)
    except Exception as exc:
        error_exit(
            f"Microphone input check failed: {exc}",
            "Grant microphone access and verify an input device is available.",
        )

    temp = tempfile.NamedTemporaryFile(prefix="voice-stt-local-check-", suffix=".wav", delete=False)
    temp_path = Path(temp.name)
    temp.close()
    write_wav(temp_path, np.zeros(16000, dtype=np.float32), 16000)
    try:
        _ = transcribe(temp_path, model)
    finally:
        temp_path.unlink(missing_ok=True)

    print(f"OK: local STT ready (model: {model})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local STT with mlx-whisper")
    parser.add_argument("--duration", "-d", type=float, help="Record from microphone for N seconds")
    parser.add_argument("--file", "-f", type=Path, help="Transcribe existing audio file")
    parser.add_argument(
        "--model",
        default="mlx-community/whisper-base-mlx",
        help="Whisper model repo (default: mlx-community/whisper-base-mlx)",
    )
    parser.add_argument(
        "--device",
        help="Input device index or name substring (use --list-devices to inspect)",
    )
    parser.add_argument("--list-devices", action="store_true", help="List available microphone devices")
    parser.add_argument("--check", action="store_true", help="Validate microphone and model")
    args = parser.parse_args()

    if args.list_devices:
        print_input_devices()
        if not args.check and args.duration is None and args.file is None:
            return

    device = resolve_device(args.device)

    if args.check:
        check_config(args.model, device)
        return

    if bool(args.duration is not None) == bool(args.file is not None):
        parser.error("Use exactly one of --duration or --file")

    ensure_apple_silicon()

    temp_path: Path | None = None
    audio_path: Path
    if args.file is not None:
        audio_path = args.file.expanduser().resolve()
        if not audio_path.exists():
            error_exit(f"Audio file does not exist: {audio_path}")
    else:
        temp_path = record_audio(args.duration if args.duration is not None else 10.0, device=device)
        audio_path = temp_path

    try:
        text = transcribe(audio_path, args.model)
        print(text)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
