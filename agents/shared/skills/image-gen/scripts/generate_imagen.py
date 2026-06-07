#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-genai"]
# ///
"""Generate images using Google's Imagen models."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import (
    OUTPUT_FORMAT_TO_EXT,
    error_exit,
    ext_for_mime,
    get_env_var,
    normalize_output_path,
    output_format_from_path,
    record_generation,
    write_output,
)

FORMAT_TO_MIME = {
    "jpeg": "image/jpeg",
    "png": "image/png",
}

PROTOCOL = {
    "protocol_version": "image-gen-provider/v1",
    "provider": "imagen",
    "default_model": "imagen-4.0-generate-001",
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
        "output_formats": ["png", "jpeg"],
        "aspect_ratios": ["1:1", "3:4", "4:3", "9:16", "16:9"],
        "provider_options": [
            "--aspect-ratio",
            "--image-size",
            "--output-format",
            "--output-compression",
            "--no-enhance-prompt",
        ],
    },
}


def print_protocol() -> None:
    print(json.dumps(PROTOCOL, indent=2, sort_keys=True))


def get_api_key() -> str:
    return get_env_var(
        ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        "https://aistudio.google.com/apikey",
    )


def check_config() -> None:
    from google import genai
    from google.genai.errors import ClientError

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)
    try:
        list(client.models.list())
        print("OK: GOOGLE_API_KEY is valid")
    except ClientError as e:
        if "API_KEY_INVALID" in str(e) or "401" in str(e):
            error_exit(
                "GOOGLE_API_KEY is invalid",
                "Get a new API key at: https://aistudio.google.com/apikey"
            )
        raise


def generate_image(
    prompt: str,
    output: Path | None,
    output_dir: Path | None = None,
    model: str = "imagen-4.0-generate-001",
    aspect_ratio: str = "1:1",
    image_size: str | None = None,
    output_format: str = "png",
    output_compression: int | None = None,
    enhance_prompt: bool | None = None,
) -> Path:
    from google import genai
    from google.genai import types
    from google.genai.errors import ClientError, ServerError

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    if output_compression is not None and output_format != "jpeg":
        error_exit("--output-compression can only be used with jpeg output")
    if output_compression is not None and not 0 <= output_compression <= 100:
        error_exit("--output-compression must be between 0 and 100")

    config_kwargs = {
        "number_of_images": 1,
        "aspect_ratio": aspect_ratio,
        "output_mime_type": FORMAT_TO_MIME[output_format],
    }
    if image_size:
        config_kwargs["image_size"] = image_size
    if output_compression is not None:
        config_kwargs["output_compression_quality"] = output_compression
    if enhance_prompt is not None:
        config_kwargs["enhance_prompt"] = enhance_prompt

    if model.startswith("imagen-4.0"):
        print(
            "Note: Google docs list Imagen 4 GA models with a 2026-06-30 "
            "discontinuation date; prefer generate_gemini.py for new work.",
            file=sys.stderr,
        )

    try:
        response = client.models.generate_images(
            model=model,
            prompt=prompt,
            config=types.GenerateImagesConfig(**config_kwargs),
        )
    except ClientError as e:
        err_str = str(e)
        if "API_KEY_INVALID" in err_str or "401" in err_str:
            error_exit(
                "GOOGLE_API_KEY is invalid",
                "Get a new API key at: https://aistudio.google.com/apikey"
            )
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            error_exit(
                "Rate limit exceeded or quota exhausted",
                "Wait a moment and try again, or check your quota at:\n"
                "https://console.cloud.google.com/apis/dashboard"
            )
        if "safety" in err_str.lower() or "blocked" in err_str.lower():
            error_exit(
                f"Content blocked for prompt: {prompt[:50]}...",
                "Try rephrasing your prompt to avoid restricted content"
            )
        error_exit(f"API error: {err_str}")
    except ServerError:
        error_exit("Google API server error", "Try again in a moment")
    except Exception as e:
        if "connect" in str(e).lower() or "network" in str(e).lower():
            error_exit("Cannot connect to Google API", "Check your internet connection")
        raise

    if not response.generated_images:
        error_exit(
            "No images in response",
            "The API returned empty results. Try a different prompt.",
        )

    image = response.generated_images[0].image
    expected_ext = ext_for_mime(image.mime_type, OUTPUT_FORMAT_TO_EXT[output_format])
    output_path = normalize_output_path(output, expected_ext, output_dir, "imagen")
    output_path = write_output(output_path, image.image_bytes)
    record_generation(
        provider="imagen",
        model=model,
        prompt=prompt,
        output_path=output_path,
        parameters={
            "aspect_ratio": aspect_ratio,
            "image_size": image_size,
            "output_format": output_format,
            "output_compression": output_compression,
            "enhance_prompt": enhance_prompt,
            "mime_type": image.mime_type,
        },
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate images with Google Imagen")
    parser.add_argument("--prompt", "-p", help="Text description of the image")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file path (default: <output-dir>/imagen-{timestamp}.{png|jpg})",
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
        default="imagen-4.0-generate-001",
        help=(
            "Model to use (default: imagen-4.0-generate-001, options: "
            "imagen-4.0-fast-generate-001, imagen-4.0-ultra-generate-001)"
        ),
    )
    parser.add_argument(
        "--aspect-ratio",
        "-a",
        default="1:1",
        choices=["1:1", "3:4", "4:3", "9:16", "16:9"],
        help="Aspect ratio (default: 1:1)",
    )
    parser.add_argument(
        "--image-size",
        "-s",
        default=None,
        help=(
            "Output image size when supported by the selected model "
            "(for example: 1K, 2K)"
        ),
    )
    parser.add_argument(
        "--output-format",
        "-f",
        choices=["png", "jpeg"],
        default=None,
        help="Generated image format (default: inferred from --output suffix, otherwise png)",
    )
    parser.add_argument(
        "--output-compression",
        type=int,
        default=None,
        help="JPEG compression quality, 0-100",
    )
    parser.add_argument(
        "--no-enhance-prompt",
        action="store_true",
        help="Disable Imagen prompt enhancement when the model supports it",
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
    if output_format not in FORMAT_TO_MIME:
        parser.error(
            "--output suffix must be .png, .jpg, or .jpeg unless --output-format is set"
        )

    output_path = generate_image(
        prompt=args.prompt,
        output=args.output,
        output_dir=args.output_dir,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        image_size=args.image_size,
        output_format=output_format,
        output_compression=args.output_compression,
        enhance_prompt=False if args.no_enhance_prompt else None,
    )
    print(output_path.resolve())


if __name__ == "__main__":
    main()
