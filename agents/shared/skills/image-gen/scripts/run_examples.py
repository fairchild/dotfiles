#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Dry-run or execute image model comparison examples."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from common import default_output_dir, load_dotenv_files


SCRIPTS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ModelPreset:
    id: str
    provider: str
    script: str
    model: str
    note: str


@dataclass(frozen=True)
class Example:
    id: str
    prompt: str
    output_ext: str
    args_by_provider: dict[str, tuple[str, ...]]


MODEL_PRESETS = [
    ModelPreset(
        id="openai:gpt-image-2",
        provider="openai",
        script="generate_openai.py",
        model="gpt-image-2",
        note="OpenAI latest GPT Image model.",
    ),
    ModelPreset(
        id="openai:gpt-image-1.5",
        provider="openai",
        script="generate_openai.py",
        model="gpt-image-1.5",
        note="OpenAI prior high-quality GPT Image model.",
    ),
    ModelPreset(
        id="openai:gpt-image-1-mini",
        provider="openai",
        script="generate_openai.py",
        model="gpt-image-1-mini",
        note="OpenAI lower-cost GPT Image model.",
    ),
    ModelPreset(
        id="gemini:nano-banana-2",
        provider="gemini",
        script="generate_gemini.py",
        model="gemini-3.1-flash-image-preview",
        note="Google Nano Banana 2, current balanced default.",
    ),
    ModelPreset(
        id="gemini:nano-banana-pro",
        provider="gemini",
        script="generate_gemini.py",
        model="gemini-3-pro-image-preview",
        note="Google Nano Banana Pro for professional assets.",
    ),
    ModelPreset(
        id="gemini:nano-banana",
        provider="gemini",
        script="generate_gemini.py",
        model="gemini-2.5-flash-image",
        note="Original Nano Banana speed/efficiency model.",
    ),
    ModelPreset(
        id="imagen:standard",
        provider="imagen",
        script="generate_imagen.py",
        model="imagen-4.0-generate-001",
        note="Imagen 4 standard GA model.",
    ),
    ModelPreset(
        id="imagen:fast",
        provider="imagen",
        script="generate_imagen.py",
        model="imagen-4.0-fast-generate-001",
        note="Imagen 4 fast GA model.",
    ),
    ModelPreset(
        id="imagen:ultra",
        provider="imagen",
        script="generate_imagen.py",
        model="imagen-4.0-ultra-generate-001",
        note="Imagen 4 highest-quality GA model.",
    ),
    ModelPreset(
        id="fal:flux-2-pro",
        provider="fal",
        script="generate_fal.py",
        model="fal-ai/flux-2-pro",
        note="fal FLUX.2 production endpoint.",
    ),
    ModelPreset(
        id="fal:flux-2-flex",
        provider="fal",
        script="generate_fal.py",
        model="fal-ai/flux-2-flex",
        note="fal FLUX.2 controllable endpoint.",
    ),
    ModelPreset(
        id="fal:flux-2",
        provider="fal",
        script="generate_fal.py",
        model="fal-ai/flux-2",
        note="fal FLUX.2 dev endpoint.",
    ),
]

DEFAULT_COMPARE_PRESETS = [
    "openai:gpt-image-2",
    "gemini:nano-banana-2",
    "gemini:nano-banana-pro",
    "imagen:ultra",
    "fal:flux-2-pro",
    "fal:flux-2-flex",
]

EXAMPLES = [
    Example(
        id="typography-poster",
        prompt=(
            "A polished editorial launch poster for a field research notebook app. "
            "The poster must include the exact large headline text FIELD NOTES, "
            "a small subtitle OBSERVE CLEARLY, and a clean grid layout with one "
            "botanical specimen illustration. Modern print design, crisp typography."
        ),
        output_ext=".png",
        args_by_provider={
            "openai": ("--size", "1536x1024", "--output-format", "png"),
            "gemini": ("--aspect-ratio", "16:9", "--image-size", "1K"),
            "imagen": ("--aspect-ratio", "16:9", "--output-format", "png"),
            "fal": ("--image-size", "landscape_16_9", "--output-format", "png"),
        },
    ),
    Example(
        id="app-icon",
        prompt=(
            "A square iOS-style app icon for a plant care journal. Use a tactile "
            "green leaf, a small brass pencil, dimensional lighting, no text, "
            "clean silhouette, centered composition."
        ),
        output_ext=".png",
        args_by_provider={
            "openai": ("--size", "1024x1024", "--output-format", "png"),
            "gemini": ("--aspect-ratio", "1:1", "--image-size", "1K"),
            "imagen": ("--aspect-ratio", "1:1", "--output-format", "png"),
            "fal": ("--image-size", "square", "--output-format", "png"),
        },
    ),
]


def preset_by_id() -> dict[str, ModelPreset]:
    return {preset.id: preset for preset in MODEL_PRESETS}


def example_by_id() -> dict[str, Example]:
    return {example.id: example for example in EXAMPLES}


def selected_presets(args: argparse.Namespace) -> list[ModelPreset]:
    presets = preset_by_id()
    ids = args.model or DEFAULT_COMPARE_PRESETS
    selected = [presets[preset_id] for preset_id in ids]
    if args.provider:
        selected = [preset for preset in selected if preset.provider == args.provider]
    return selected


def selected_examples(args: argparse.Namespace) -> list[Example]:
    examples = example_by_id()
    if args.example == "all":
        return EXAMPLES
    return [examples[args.example]]


def command_for(
    preset: ModelPreset,
    example: Example,
    output_dir: Path,
) -> tuple[list[str], Path]:
    filename = f"{example.id}__{preset.id.replace(':', '-').replace('/', '-')}"
    output = output_dir / f"{filename}{example.output_ext}"
    provider_args = list(example.args_by_provider.get(preset.provider, ()))
    command = [
        str(SCRIPTS_DIR / preset.script),
        "--model",
        preset.model,
        "--prompt",
        example.prompt,
        "--output",
        str(output),
        *provider_args,
    ]
    return command, output


def print_list() -> None:
    print("Model presets:")
    for preset in MODEL_PRESETS:
        marker = "default" if preset.id in DEFAULT_COMPARE_PRESETS else "available"
        print(f"  {preset.id} ({marker}) - {preset.note}")

    print("\nExamples:")
    for example in EXAMPLES:
        print(f"  {example.id}")


def run_command(command: list[str], timeout: int) -> dict[str, object]:
    started = time.monotonic()
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    duration = time.monotonic() - started
    stdout_lines = [line for line in result.stdout.splitlines() if line.strip()]
    output_path = stdout_lines[-1] if stdout_lines else None
    return {
        "command": command,
        "returncode": result.returncode,
        "duration_seconds": round(duration, 2),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "output_path": output_path,
    }


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def initial_manifest(
    *,
    output_dir: Path,
    examples: list[Example],
    presets: list[ModelPreset],
) -> dict[str, object]:
    prompts = {example.id: example.prompt for example in examples}
    return {
        "id": output_dir.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir.resolve()),
        "examples": [example.id for example in examples],
        "prompts": prompts,
        "prompt": examples[0].prompt if len(examples) == 1 else "",
        "presets": [preset.id for preset in presets],
        "outputs": [],
        "runs": [],
    }


def output_entry(
    *,
    preset: ModelPreset,
    example: Example,
    result: dict[str, object],
    output_dir: Path,
) -> dict[str, object] | None:
    if result.get("returncode") != 0 or not result.get("output_path"):
        return None

    output_path = Path(str(result["output_path"])).expanduser()
    try:
        relative_path = str(output_path.resolve().relative_to(output_dir.resolve()))
    except ValueError:
        relative_path = str(output_path)

    return {
        "candidate_id": f"{example.id}:{preset.id}",
        "example": example.id,
        "model": preset.model,
        "path": relative_path,
        "preset": preset.id,
        "provider": preset.provider,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run image-gen comparison examples")
    parser.add_argument("--generate", action="store_true", help="Run paid image generation")
    parser.add_argument("--list", action="store_true", help="List presets and examples")
    parser.add_argument(
        "--provider",
        choices=sorted({preset.provider for preset in MODEL_PRESETS}),
        help="Restrict to one provider",
    )
    parser.add_argument(
        "--model",
        action="append",
        choices=sorted(preset_by_id()),
        help="Run one model preset; repeat for multiple. Defaults to current comparison set.",
    )
    parser.add_argument(
        "--example",
        choices=sorted([example.id for example in EXAMPLES] + ["all"]),
        default="typography-poster",
        help="Example prompt to run",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: outputs/examples/{timestamp})",
    )
    parser.add_argument("--timeout", type=int, default=300, help="Seconds per generation")
    args = parser.parse_args()

    if args.list:
        print_list()
        return

    presets = selected_presets(args)
    examples = selected_examples(args)
    if not presets:
        parser.error("no model presets selected")

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = args.output_dir or default_output_dir() / "examples" / run_id

    commands = [
        (preset, example, *command_for(preset, example, output_dir))
        for example in examples
        for preset in presets
    ]

    if not args.generate:
        print("Dry run. Add --generate to make paid API calls.")
        print(f"Output directory would be: {output_dir.resolve()}")
        for preset, example, command, _output in commands:
            print(f"\n# {example.id} / {preset.id}")
            print(shlex.join(command))
        return

    load_dotenv_files()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    manifest = initial_manifest(output_dir=output_dir, examples=examples, presets=presets)
    write_manifest(manifest_path, manifest)

    failures = 0
    for preset, example, command, expected_output in commands:
        print(f"{example.id} / {preset.id} ... ", end="", flush=True)
        try:
            result = run_command(command, args.timeout)
        except subprocess.TimeoutExpired:
            result = {
                "command": command,
                "returncode": 124,
                "duration_seconds": args.timeout,
                "stdout": "",
                "stderr": f"Timed out after {args.timeout}s",
                "output_path": None,
            }

        result.update(
            {
                "example": example.id,
                "preset": preset.id,
                "expected_output": str(expected_output),
            }
        )
        manifest["runs"].append(result)
        entry = output_entry(
            preset=preset,
            example=example,
            result=result,
            output_dir=output_dir,
        )
        if entry:
            manifest["outputs"].append(entry)
        write_manifest(manifest_path, manifest)

        ok = result["returncode"] == 0 and result.get("output_path")
        print("OK" if ok else "failed")
        if not ok:
            failures += 1

    print(manifest_path.resolve())
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
