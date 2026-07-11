#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["fal-client", "requests"]
# ///
"""Generate images using fal.ai's Flux models."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from common import (
    error_exit,
    ext_for_mime,
    get_env_var,
    normalize_output_path,
    output_format_from_path,
    record_generation,
    write_output,
)

FORMAT_TO_EXT = {
    "jpeg": ".jpg",
    "png": ".png",
}

PROTOCOL = {
    "protocol_version": "image-gen-provider/v1",
    "provider": "fal",
    "default_model": "fal-ai/flux-2-pro",
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
        "output_formats": ["jpeg", "png"],
        "image_sizes": [
            "square_hd",
            "square",
            "portrait_4_3",
            "portrait_16_9",
            "landscape_4_3",
            "landscape_16_9",
        ],
        "provider_options": [
            "--image-size",
            "--output-format",
            "--seed",
            "--guidance-scale",
            "--num-inference-steps",
            "--num-images",
        ],
    },
}


def print_protocol() -> None:
    print(json.dumps(PROTOCOL, indent=2, sort_keys=True))


def get_api_key() -> str:
    return get_env_var(("FAL_KEY",), "https://fal.ai/dashboard/keys")


def check_config() -> None:
    import fal_client

    api_key = get_api_key()
    os.environ["FAL_KEY"] = api_key
    try:
        fal_client.auth.fetch_auth_credentials()
        print("OK: FAL_KEY is set")
    except Exception:
        error_exit(
            "FAL_KEY could not be loaded",
            "Get a new API key at: https://fal.ai/dashboard/keys",
        )


def generate_image(
    prompt: str,
    output: Path | None,
    output_dir: Path | None = None,
    model: str = "fal-ai/flux-2-pro",
    image_size: str | None = None,
    output_format: str = "jpeg",
    seed: int | None = None,
    guidance_scale: float | None = None,
    num_inference_steps: int | None = None,
    num_images: int | None = None,
) -> Path:
    import fal_client
    import requests
    from fal_client.client import FalClientHTTPError

    api_key = get_api_key()
    os.environ["FAL_KEY"] = api_key

    arguments: dict[str, object] = {
        "prompt": prompt,
        "output_format": output_format,
    }
    if image_size:
        arguments["image_size"] = image_size
    if seed is not None:
        arguments["seed"] = seed
    if guidance_scale is not None:
        arguments["guidance_scale"] = guidance_scale
    if num_inference_steps is not None:
        arguments["num_inference_steps"] = num_inference_steps
    if num_images is not None:
        arguments["num_images"] = num_images

    try:
        result = fal_client.subscribe(
            model,
            arguments=arguments,
        )
    except FalClientHTTPError as e:
        err_str = str(e)
        if "401" in err_str or "Unauthorized" in err_str or "Authentication is required" in err_str:
            error_exit(
                "FAL_KEY is invalid or expired",
                "Get a new API key at: https://fal.ai/dashboard/keys"
            )
        if "429" in err_str or "rate" in err_str.lower():
            error_exit(
                "Rate limit exceeded",
                "Wait a moment and try again, or check your usage at:\n"
                "https://fal.ai/dashboard"
            )
        if "402" in err_str or "payment" in err_str.lower() or "credit" in err_str.lower():
            error_exit(
                "Insufficient credits",
                "Add credits at: https://fal.ai/dashboard/billing"
            )
        error_exit(f"API error: {err_str}")
    except Exception as e:
        if "connect" in str(e).lower() or "network" in str(e).lower():
            error_exit("Cannot connect to fal.ai API", "Check your internet connection")
        raise

    images = result.get("images", [])
    if not images:
        error_exit(
            "No images in response",
            "The API returned empty results. Try a different prompt.",
        )

    image_url = images[0].get("url")
    if not image_url:
        error_exit("Image response did not include a URL")

    if image_url.startswith("data:"):
        error_exit(
            "fal.ai returned an inline data URI",
            "This script expects a downloadable image URL. "
            "Retry without sync-mode models/settings.",
        )

    try:
        image_response = requests.get(image_url, timeout=60)
        image_response.raise_for_status()
    except requests.RequestException as e:
        error_exit(f"Failed to download image: {e}", "Check your internet connection")

    content_type = image_response.headers.get("content-type", "").split(";")[0].strip()
    actual_ext = ext_for_mime(content_type, FORMAT_TO_EXT[output_format])
    if actual_ext == ".jpg":
        url_path = Path(unquote(urlparse(image_url).path))
        if url_path.suffix.lower() == ".png":
            actual_ext = ".png"

    output_path = normalize_output_path(output, actual_ext, output_dir, "fal")
    output_path = write_output(output_path, image_response.content)
    record_generation(
        provider="fal",
        model=model,
        prompt=prompt,
        output_path=output_path,
        parameters={
            "image_size": image_size,
            "output_format": output_format,
            "seed": seed,
            "guidance_scale": guidance_scale,
            "num_inference_steps": num_inference_steps,
            "num_images": num_images,
            "content_type": content_type,
        },
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate images with fal.ai Flux")
    parser.add_argument("--prompt", "-p", help="Text description of the image")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file path (default: <output-dir>/fal-{timestamp}.{ext})",
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
        default="fal-ai/flux-2-pro",
        help="Model to use (default: fal-ai/flux-2-pro)",
    )
    parser.add_argument(
        "--image-size",
        "-s",
        default=None,
        choices=[
            "square_hd",
            "square",
            "portrait_4_3",
            "portrait_16_9",
            "landscape_4_3",
            "landscape_16_9",
        ],
        help="fal image size preset",
    )
    parser.add_argument(
        "--output-format",
        "-f",
        choices=["jpeg", "png"],
        default=None,
        help="Generated image format (default: inferred from --output suffix, otherwise jpeg)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for repeatable output when supported",
    )
    parser.add_argument(
        "--guidance-scale",
        type=float,
        default=None,
        help="Prompt guidance scale when supported",
    )
    parser.add_argument(
        "--num-inference-steps",
        type=int,
        default=None,
        help="Inference steps when supported",
    )
    parser.add_argument(
        "--num-images",
        type=int,
        default=None,
        help="Number of images when supported",
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

    output_format = args.output_format or output_format_from_path(args.output, default="jpeg")
    if output_format not in FORMAT_TO_EXT:
        parser.error(
            "--output suffix must be .png, .jpg, or .jpeg unless --output-format is set"
        )

    output_path = generate_image(
        prompt=args.prompt,
        output=args.output,
        output_dir=args.output_dir,
        model=args.model,
        image_size=args.image_size,
        output_format=output_format,
        seed=args.seed,
        guidance_scale=args.guidance_scale,
        num_inference_steps=args.num_inference_steps,
        num_images=args.num_images,
    )
    print(output_path.resolve())


if __name__ == "__main__":
    main()
