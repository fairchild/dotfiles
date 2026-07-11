---
name: image-gen
description: Generate images from prompts using AI APIs (OpenAI GPT Image, Google Gemini/Nano Banana, Google Imagen, fal.ai Flux). Use when the user asks to generate, create, make, render, or produce an image, icon, visual asset, illustration, mockup, texture, poster, or other raster image file.
license: Apache-2.0
---

# Image Generation

Generate raster images by running the bundled provider scripts. Do not stop at a prompt description when the user asked for an image file.

After generation, return the absolute output path and, when the client supports it, render the image with Markdown:

```markdown
![generated image](/absolute/path/to/image.png)
```

## Choose A Provider

| Use case | Provider/script | Notes |
|----------|-----------------|-------|
| General prompt-to-image default | `generate_openai.py` | Defaults to `gpt-image-2`; strong output controls. |
| Gemini/Nano Banana output | `generate_gemini.py` | Defaults to Nano Banana 2 (`gemini-3.1-flash-image-preview`). |
| Complex Gemini or text-heavy visual work | `generate_gemini.py --model gemini-3-pro-image-preview` | Nano Banana Pro; supports 1K/2K/4K size controls. |
| Specific Imagen requirement | `generate_imagen.py` | Imagen 4 GA models are listed by Google with a 2026-06-30 discontinuation date; prefer Gemini for new work unless Imagen is requested. |
| Flux or fal model ecosystem | `generate_fal.py` | Defaults to `fal-ai/flux-2-pro`; supports fal size presets, seed, output format, and optional model-specific controls. |

For the current comparison model matrix, read `references/current-models.md`. For model/API refreshes and long-term data handling, read `references/maintenance-workflow.md`. For the implemented design and provider protocol approach, read `references/provider-protocol-architecture.html`. For why generated outputs and local history live in ignored skill-local directories, read `references/storage-policy.md`.

## Command Pattern

The Python entrypoints are executable UV scripts. Prefer direct execution:

```bash
~/.claude/skills/image-gen/scripts/<script>.py \
  --prompt "a cat wearing a top hat" \
  --output /tmp/cat.png
```

`uv run --script ~/.claude/skills/image-gen/scripts/<script>.py ...` remains a valid fallback if a copied checkout has lost executable bits.

Provider scripts are image generation adapters. Keep their interface stable: executable UV script, `--prompt`, `--output`, `--output-dir`, `--model`, `--check`, `--protocol`, successful generation history, and resolved output path as the final stdout line.

`scripts/common.py` is the only shared local helper.

Common examples:

```bash
# Default OpenAI path
~/.claude/skills/image-gen/scripts/generate_openai.py \
  --prompt "a cat wearing a top hat" \
  --output /tmp/cat.png

# Gemini Pro / Nano Banana Pro
~/.claude/skills/image-gen/scripts/generate_gemini.py \
  --model gemini-3-pro-image-preview \
  --prompt "a typography-forward launch poster for a boutique coffee app" \
  --output /tmp/poster.png \
  --aspect-ratio 16:9 \
  --image-size 2K

# fal with repeatability
~/.claude/skills/image-gen/scripts/generate_fal.py \
  --prompt "isometric game asset of a glass greenhouse" \
  --output /tmp/greenhouse.jpg \
  --seed 1234
```

Use each script's `--help` as the full option reference:

```bash
~/.claude/skills/image-gen/scripts/generate_openai.py --help
```

## Comparison Runs

Use `run_examples.py` to compare current model presets. It dry-runs by default and only makes paid API calls with `--generate`.

```bash
~/.claude/skills/image-gen/scripts/run_examples.py --list
~/.claude/skills/image-gen/scripts/run_examples.py
~/.claude/skills/image-gen/scripts/run_examples.py --generate --example typography-poster
```

Single-example generated manifests are reviewable directly with `review_gallery.py`.

Use `review_gallery.py` for local winner selection, image-order ranking, an optional comment, and one/all candidate regeneration:

```bash
~/.claude/skills/image-gen/scripts/review_gallery.py --run-dir <comparison-run-dir>
```

Click-to-rank assigns rank 1 to the first distinct image clicked, rank 2 to the second, rank 3 to the third, then leaves remaining unclicked images in current order. Clicking an already-ranked image or clicking after a completed pass starts a fresh ranking pass from rank 1.

The review page opens image-only. Tap or click outside the image cards and controls to toggle prompt, actions, status, and comment; press `Esc` to hide them. `R` reveals or hides only provider/model details, even while the rest of the chrome stays hidden.

After changing the review UI or generating comparison outputs, run the visual evaluator and inspect its screenshots/checks before reporting:

```bash
~/.claude/skills/image-gen/scripts/evaluate_review_gallery.py --run-dir <comparison-run-dir>
```

It captures default, interaction, and mobile screenshots under `outputs/evaluations/` and checks that the default view is image-only, images load, metadata does not overlap the image, click-to-rank works, keyboard ranking works, `R` toggles details, and `S` saves with a visual indicator. With `--run-dir`, it serves a temporary copy so validation does not mutate the original comparison run.

## Common Options

- `--prompt`: Required prompt.
- `--output`, `-o`: Output path. Parent directories are created automatically.
- `--output-dir`: Default directory when `--output` is omitted.
- `--model`: Override the default provider model.
- `--aspect-ratio`, `-a`: Gemini and Imagen aspect ratio.
- `--size` or `--image-size`, `-s`: Provider-specific output size control.
- `--output-format`, `-f`: Use when the file suffix should not determine PNG/JPEG/WebP.
- `--check`: Validate provider configuration without generating an image.
- `--protocol`: Print provider adapter protocol JSON without API keys.

## Setup And Checks

| Provider | Env var | Key URL |
|----------|---------|---------|
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| Google | `GOOGLE_API_KEY` or `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| fal.ai | `FAL_KEY` | https://fal.ai/dashboard/keys |

Scripts read exported variables first, then simple `KEY=value` lines from `.env` in the current directory and `~/.env`.

If `--output` is omitted, scripts save under `skills/image-gen/outputs/` by default. Override that with `IMAGE_GEN_OUTPUT_DIR` or `--output-dir`. The outputs directory is intentionally gitignored except for its README.

Successful generations are also logged to `skills/image-gen/data/generations.jsonl` by default. Set `IMAGE_GEN_DISABLE_HISTORY=1` for sensitive prompts, or `IMAGE_GEN_DATA_DIR=/path/to/dir` to move local history elsewhere.

Check keys without spending generation credits:

```bash
~/.claude/skills/image-gen/scripts/generate_openai.py --check
~/.claude/skills/image-gen/scripts/generate_gemini.py --check
~/.claude/skills/image-gen/scripts/generate_imagen.py --check
~/.claude/skills/image-gen/scripts/generate_fal.py --check
```

Inspect provider protocol metadata without API keys:

```bash
~/.claude/skills/image-gen/scripts/generate_openai.py --protocol
~/.claude/skills/image-gen/scripts/check_protocol.py
```

Generation may incur provider costs. If a key is missing or invalid, fix the env var rather than changing the script.

## Output Handling

- Scripts print the resolved output path on success.
- If the provider returns a different image MIME type than the requested suffix, scripts save with the corrected suffix and print a note.
- OpenAI can request PNG, JPEG, or WebP.
- Imagen can request PNG or JPEG.
- Gemini and fal.ai save using the MIME type returned by the API.

## Testing

```bash
~/.claude/skills/image-gen/scripts/check_protocol.py
~/.claude/skills/image-gen/tests/test_image_gen.py
~/.claude/skills/image-gen/tests/test_image_gen.py --check-env
~/.claude/skills/image-gen/tests/test_image_gen.py --generate --provider openai
```

Default testing is free and does not require API keys. `check_protocol.py` is the focused adapter-contract check and is also run by PR validation when `skills/image-gen/` changes. `--check-env` reports configured keys. `--generate` makes real API calls and stores outputs in `skills/image-gen/outputs/test-runs/`.

## References

- OpenAI image generation: https://platform.openai.com/docs/guides/image-generation
- Gemini image generation: https://ai.google.dev/gemini-api/docs/image-generation
- Imagen 4 model lifecycle: https://cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/4-0-generate
- fal Python client: https://fal.ai/docs/api-reference/client-libraries/python
- Provider pricing: https://platform.openai.com/docs/pricing, https://ai.google.dev/pricing, https://cloud.google.com/vertex-ai/generative-ai/pricing, https://fal.ai/pricing
