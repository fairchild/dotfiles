# Current Image Model Matrix

Last checked: 2026-05-16.

Use this when updating defaults or selecting models for `scripts/run_examples.py`. Prefer official provider docs over third-party lists.

## OpenAI

OpenAI's image generation guide lists `gpt-image-2` as the latest GPT Image model and names the GPT Image family as `gpt-image-2`, `gpt-image-1.5`, `gpt-image-1`, and `gpt-image-1-mini`.

Comparison presets:

| Preset | Model ID | Role |
|--------|----------|------|
| `openai:gpt-image-2` | `gpt-image-2` | Current default and highest-capability model. |
| `openai:gpt-image-1.5` | `gpt-image-1.5` | Prior high-quality model for regression comparison. |
| `openai:gpt-image-1-mini` | `gpt-image-1-mini` | Lower-cost comparison point. |

Source: https://platform.openai.com/docs/guides/image-generation

## Google Gemini / Nano Banana

Google documents three Nano Banana image models in the Gemini API:

| Preset | Model ID | Role |
|--------|----------|------|
| `gemini:nano-banana-2` | `gemini-3.1-flash-image-preview` | Go-to balanced image generation model. |
| `gemini:nano-banana-pro` | `gemini-3-pro-image-preview` | Professional asset production and complex instructions. |
| `gemini:nano-banana` | `gemini-2.5-flash-image` | Original speed/efficiency model. |

Gemini 3.1 Flash Image Preview supports `512`, `1K`, `2K`, and `4K` output size controls. Gemini 3 Pro Image Preview supports `1K`, `2K`, and `4K`; Gemini 2.5 Flash Image is fixed around 1024px output.

Source: https://ai.google.dev/gemini-api/docs/image-generation

## Google Imagen

Imagen 4 is still available, but Google lists the GA Imagen 4 models with a June 30, 2026 discontinuation date and maps their migration target to `gemini-2.5-flash-image`.

Comparison presets:

| Preset | Model ID | Role |
|--------|----------|------|
| `imagen:standard` | `imagen-4.0-generate-001` | Standard Imagen 4 output. |
| `imagen:fast` | `imagen-4.0-fast-generate-001` | Lower-latency Imagen 4 output. |
| `imagen:ultra` | `imagen-4.0-ultra-generate-001` | Highest-quality Imagen 4 output. |

Source: https://cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/4-0-generate

## fal.ai / FLUX

For FLUX-specific comparison, use the FLUX.2 endpoints. fal also exposes OpenAI and Gemini image models, but those duplicate the direct providers above.

Comparison presets:

| Preset | Model ID | Role |
|--------|----------|------|
| `fal:flux-2-pro` | `fal-ai/flux-2-pro` | Production FLUX.2 endpoint with fixed pro settings. |
| `fal:flux-2-flex` | `fal-ai/flux-2-flex` | Controllable FLUX.2 endpoint with guidance and step controls. |
| `fal:flux-2` | `fal-ai/flux-2` | FLUX.2 dev endpoint for fast iteration and experimentation. |

Sources:
- https://blog.fal.ai/flux-2-is-now-available-on-fal/
- https://fal.ai/models/fal-ai/flux-2-pro
- https://fal.ai/models/fal-ai/flux-2-flex
- https://fal.ai/models/fal-ai/flux-2
