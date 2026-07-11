#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["openai"]
# ///
"""Generate images using OpenAI GPT Image models."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from common import (
    OUTPUT_FORMAT_TO_EXT,
    error_exit,
    get_env_var,
    normalize_output_path,
    output_format_from_path,
    record_generation,
    write_output,
)


PROTOCOL = {
    "protocol_version": "image-gen-provider/v1",
    "provider": "openai",
    "default_model": "gpt-image-2",
    "required_options": [
        "--prompt",
        "--output",
        "--output-dir",
        "--model",
        "--check",
        "--protocol",
    ],
    "final_stdout": "resolved_output_path",
    "history": "generations.jsonl",
    "local_helper_imports": ["common"],
    "supports": {
        "output_formats": ["png", "jpeg", "webp"],
        "size_options": ["auto", "1024x1024", "1024x1536", "1536x1024"],
        "provider_options": [
            "--size",
            "--quality",
            "--output-format",
            "--output-compression",
            "--background",
        ],
    },
}


def print_protocol() -> None:
    print(json.dumps(PROTOCOL, indent=2, sort_keys=True))


def get_api_key() -> str:
    return get_env_var(("OPENAI_API_KEY",), "https://platform.openai.com/api-keys")


def check_config() -> None:
    from openai import APIConnectionError, AuthenticationError, OpenAI

    api_key = get_api_key()
    client = OpenAI(api_key=api_key)
    try:
        client.models.list()
        print("OK: OPENAI_API_KEY is valid")
    except AuthenticationError:
        error_exit(
            "OPENAI_API_KEY is invalid or expired",
            "Get a new API key at: https://platform.openai.com/api-keys"
        )
    except APIConnectionError:
        error_exit("Cannot connect to OpenAI API", "Check your internet connection")


def generate_image(
    prompt: str,
    output: Path | None,
    output_dir: Path | None = None,
    model: str = "gpt-image-2",
    size: str = "auto",
    quality: str = "auto",
    output_format: str = "png",
    output_compression: int | None = None,
    background: str = "auto",
) -> Path:
    from openai import APIConnectionError, AuthenticationError, BadRequestError, OpenAI, RateLimitError

    api_key = get_api_key()
    client = OpenAI(api_key=api_key)

    if output_compression is not None and output_format not in {"jpeg", "webp"}:
        error_exit("--output-compression can only be used with jpeg or webp output")
    if output_compression is not None and not 0 <= output_compression <= 100:
        error_exit("--output-compression must be between 0 and 100")
    if model == "gpt-image-2" and background == "transparent":
        error_exit(
            "gpt-image-2 does not support transparent backgrounds",
            "Use --background opaque/auto, or use a GPT Image 1.x model "
            "that supports transparency.",
        )

    request_args = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": quality,
        "output_format": output_format,
        "background": background,
    }
    if output_compression is not None:
        request_args["output_compression"] = output_compression

    try:
        response = client.images.generate(**request_args)
    except AuthenticationError:
        error_exit(
            "OPENAI_API_KEY is invalid or expired",
            "Get a new API key at: https://platform.openai.com/api-keys"
        )
    except APIConnectionError:
        error_exit("Cannot connect to OpenAI API", "Check your internet connection")
    except RateLimitError:
        error_exit(
            "Rate limit exceeded or insufficient quota",
            "Wait a moment and try again, or check your usage at:\n"
            "https://platform.openai.com/usage"
        )
    except BadRequestError as e:
        if "content_policy" in str(e).lower() or "safety" in str(e).lower():
            error_exit(
                f"Content policy violation for prompt: {prompt[:50]}...",
                "Try rephrasing your prompt to avoid restricted content"
            )
        raise

    b64_json = response.data[0].b64_json
    if not b64_json:
        error_exit("No image data in response", "The API returned an empty image result.")

    image_data = base64.b64decode(b64_json)
    expected_ext = OUTPUT_FORMAT_TO_EXT[output_format]
    output_path = normalize_output_path(output, expected_ext, output_dir, "openai")
    output_path = write_output(output_path, image_data)
    record_generation(
        provider="openai",
        model=model,
        prompt=prompt,
        output_path=output_path,
        parameters={
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "output_compression": output_compression,
            "background": background,
        },
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate images with OpenAI GPT Image")
    parser.add_argument("--prompt", "-p", help="Text description of the image")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file path (default: <output-dir>/openai-{timestamp}.{png|jpg|webp})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Default output directory when --output is omitted",
    )
    parser.add_argument(
        "--model",
        "-m",
        default="gpt-image-2",
        help=(
            "Model to use (default: gpt-image-2; common alternatives: "
            "gpt-image-1.5, gpt-image-1, gpt-image-1-mini)"
        ),
    )
    parser.add_argument(
        "--size",
        "-s",
        default="auto",
        help="Image size (default: auto; common sizes: 1024x1024, 1024x1536, 1536x1024)",
    )
    parser.add_argument(
        "--quality",
        "-q",
        default="auto",
        choices=["low", "medium", "high", "auto"],
        help="Image quality (default: auto)",
    )
    parser.add_argument(
        "--output-format",
        "-f",
        choices=["png", "jpeg", "webp"],
        default=None,
        help="Generated image format (default: inferred from --output suffix, otherwise png)",
    )
    parser.add_argument(
        "--output-compression",
        type=int,
        default=None,
        help="JPEG/WebP compression level, 0-100",
    )
    parser.add_argument(
        "--background",
        choices=["auto", "opaque", "transparent"],
        default="auto",
        help="Background mode (default: auto; transparent requires a model that supports it)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate API key configuration without generating an image",
    )
    parser.add_argument(
        "--protocol",
        action="store_true",
        help="Print the provider adapter protocol JSON without requiring API keys",
    )
    args = parser.parse_args()

    if args.protocol:
        print_protocol()
        return

    if args.check:
        check_config()
        return

    if not args.prompt:
        parser.error("--prompt is required unless using --check")

    output_format = args.output_format or output_format_from_path(args.output, default="png")

    output_path = generate_image(
        prompt=args.prompt,
        output=args.output,
        output_dir=args.output_dir,
        model=args.model,
        size=args.size,
        quality=args.quality,
        output_format=output_format,
        output_compression=args.output_compression,
        background=args.background,
    )
    print(output_path.resolve())


if __name__ == "__main__":
    main()
