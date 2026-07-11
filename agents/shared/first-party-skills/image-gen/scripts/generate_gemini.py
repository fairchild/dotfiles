#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-genai"]
# ///
"""Generate images using Google's Gemini image models (Nano Banana)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    error_exit,
    ext_for_mime,
    get_env_var,
    normalize_output_path,
    record_generation,
    write_output,
)


PROTOCOL = {
    "protocol_version": "image-gen-provider/v1",
    "provider": "gemini",
    "default_model": "gemini-3.1-flash-image-preview",
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
        "output_formats": ["provider-returned-mime"],
        "aspect_ratios": [
            "1:1",
            "1:4",
            "1:8",
            "2:3",
            "3:2",
            "3:4",
            "4:1",
            "4:3",
            "4:5",
            "5:4",
            "8:1",
            "9:16",
            "16:9",
            "21:9",
        ],
        "image_sizes": ["512", "1K", "2K", "4K"],
        "provider_options": ["--aspect-ratio", "--image-size"],
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
    model: str = "gemini-3.1-flash-image-preview",
    aspect_ratio: str = "1:1",
    image_size: str | None = None,
) -> Path:
    from google import genai
    from google.genai import types
    from google.genai.errors import ClientError, ServerError

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    image_config_kwargs = {"aspect_ratio": aspect_ratio}
    if image_size:
        image_config_kwargs["image_size"] = image_size

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["Image"],
                image_config=types.ImageConfig(**image_config_kwargs),
            ),
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

    for part in response.parts:
        if part.inline_data is not None:
            mime_type = part.inline_data.mime_type
            actual_ext = ext_for_mime(mime_type)
            output_path = normalize_output_path(output, actual_ext, output_dir, "gemini")
            output_path = write_output(output_path, part.inline_data.data)
            record_generation(
                provider="gemini",
                model=model,
                prompt=prompt,
                output_path=output_path,
                parameters={
                    "aspect_ratio": aspect_ratio,
                    "image_size": image_size,
                    "mime_type": mime_type,
                },
            )
            return output_path

    error_exit("No image in response", "The API returned empty results. Try a different prompt.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate images with Google Gemini (Nano Banana)")
    parser.add_argument("--prompt", "-p", help="Text description of the image")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file path (default: <output-dir>/gemini-{timestamp}.{ext})",
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
        default="gemini-3.1-flash-image-preview",
        help=(
            "Model to use (default: gemini-3.1-flash-image-preview aka "
            "Nano Banana 2; use gemini-3-pro-image-preview for Pro)"
        ),
    )
    parser.add_argument(
        "--aspect-ratio",
        "-a",
        default="1:1",
        choices=[
            "1:1",
            "1:4",
            "1:8",
            "2:3",
            "3:2",
            "3:4",
            "4:1",
            "4:3",
            "4:5",
            "5:4",
            "8:1",
            "9:16",
            "16:9",
            "21:9",
        ],
        help="Aspect ratio (default: 1:1)",
    )
    parser.add_argument(
        "--image-size",
        "-s",
        default=None,
        choices=["512", "1K", "2K", "4K"],
        help="Output size for supported models (options: 512, 1K, 2K, 4K)",
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

    output_path = generate_image(
        prompt=args.prompt,
        output=args.output,
        output_dir=args.output_dir,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        image_size=args.image_size,
    )
    print(output_path.resolve())


if __name__ == "__main__":
    main()
