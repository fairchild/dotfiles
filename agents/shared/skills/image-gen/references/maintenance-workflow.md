# Image-Gen Maintenance Workflow

Use this workflow when new image models, provider APIs, pricing, output formats, or comparison needs appear.

## Storage Model

Keep generated history local by default.

| Path | Git status | Purpose |
|------|------------|---------|
| `outputs/` | ignored except `README.md` | Generated images, comparison galleries, per-run manifests. |
| `data/` | ignored except `README.md` | Local long-term usage metadata such as `generations.jsonl`, `rankings.jsonl`, and `regenerations.jsonl`. |
| `references/` | tracked | Maintainer docs, model matrices, API notes, workflow docs. |
| `assets/` | tracked when safe | Reusable prompt packs, gallery templates, masks, reference images, style boards. |

Do not put routine generated outputs in `assets/`. Use `assets/` only for stable inputs that future runs should reuse.

This is a repo-local convention for this skill, not a general Agent Skills standard. See `references/storage-policy.md` for the research notes, rationale, and rules.

## Local History

Every provider script records successful generations to `data/generations.jsonl` unless disabled.

Each entry includes:

- UTC timestamp
- provider and model
- full prompt plus `prompt_sha256`
- absolute output path and skill-relative output path when possible
- output size and detected PNG/JPEG dimensions
- non-secret generation parameters

Controls:

```bash
# Disable prompt/output logging for sensitive generations
IMAGE_GEN_DISABLE_HISTORY=1 skills/image-gen/scripts/generate_openai.py ...

# Move local history outside the repo
IMAGE_GEN_DATA_DIR=/path/to/image-gen-history skills/image-gen/scripts/generate_gemini.py ...

# Move generated images outside the repo
IMAGE_GEN_OUTPUT_DIR=/path/to/image-gen-outputs skills/image-gen/scripts/generate_fal.py ...
```

The Python entrypoints are executable UV scripts. Prefer direct execution in docs and examples; `uv run --script ...` remains a fallback when executable bits are unavailable.

The local history is useful for later analysis of prompts, model drift, cost/performance notes, and generated-image provenance. It is not a public benchmark and should stay out of git.

## Update Cycle

1. Check official provider docs first.
   - OpenAI: https://platform.openai.com/docs/guides/image-generation
   - Gemini: https://ai.google.dev/gemini-api/docs/image-generation
   - Imagen: https://cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/4-0-generate
   - fal: provider model pages and OpenAPI schemas on https://fal.ai/models

2. Update `references/current-models.md`.
   - Change the `Last checked` date.
   - Add exact model IDs, roles, lifecycle dates, and source URLs.
   - Keep drift-prone facts out of `SKILL.md` unless they affect default agent behavior.

3. Update provider scripts.
   - Prefer small provider-specific scripts over a generic abstraction that hides API differences.
   - Keep shared behavior in `scripts/common.py`: output paths, env loading, MIME handling, history logging.
   - Add only CLI flags that are stable and useful for agent workflows.
   - Preserve the provider adapter protocol: executable UV script, `--prompt`, `--output`, `--output-dir`, `--model`, `--check`, `--protocol`, history logging, and final stdout line as the resolved output path.
   - Keep `scripts/common.py` as the only shared local helper import for provider scripts.
   - Keep `--protocol` free of provider credentials and paid API calls.
   - See `references/provider-protocol-architecture.html` when changing the adapter contract or explaining how the skill works.

4. Update comparison presets in `scripts/run_examples.py`.
   - Keep a small default comparison set that covers current best defaults.
   - Add older or niche models as available presets, not necessarily default presets.
   - Use prompts that reveal meaningful differences: text rendering, instruction following, icon/asset style, layout fidelity, and exact object constraints.
   - Keep single-example generated manifests compatible with `scripts/review_gallery.py`.

5. Run free verification.

```bash
skills/image-gen/scripts/check_protocol.py
skills/image-gen/tests/test_image_gen.py
skills/image-gen/scripts/run_examples.py --list
skills/image-gen/scripts/run_examples.py
skills/image-gen/scripts/generate_openai.py --help
skills/image-gen/scripts/generate_gemini.py --help
skills/image-gen/scripts/generate_imagen.py --help
skills/image-gen/scripts/generate_fal.py --help
skills/image-gen/scripts/generate_openai.py --protocol
```

`check_protocol.py` is the focused adapter-contract check. It runs without API keys or provider SDK imports, and PR validation runs it automatically when `skills/image-gen/` changes.

6. Run paid comparisons only when useful.

```bash
skills/image-gen/scripts/run_examples.py --generate --example all
```

Inspect the run directory under `outputs/examples/<timestamp>/`, open the generated gallery when present, and keep the manifest with the images. Do not commit generated outputs.

Review comparison outputs with:

```bash
skills/image-gen/scripts/review_gallery.py --run-dir <comparison-run-dir>
```

The review server saves `feedback.json`, copies the selected winner to `winner.<ext>`, appends rankings to `data/rankings.jsonl`, and can regenerate one or all candidates by invoking the provider scripts.

After changing the review gallery or creating a comparison run that needs visual QA, run the evaluator:

```bash
skills/image-gen/scripts/evaluate_review_gallery.py --run-dir <comparison-run-dir>
```

It writes screenshots and machine-readable checks under `outputs/evaluations/<run-id>/<timestamp>/`. Inspect `default.png`, `interaction.png`, `mobile.png`, and `checks.json` before handing the gallery back to the user. With `--run-dir`, the evaluator serves a copied run under the evaluation directory so save and ranking checks do not mutate the source comparison. This is the place to grow the agent-driven evaluation loop: capture the rendered gallery, verify the default image-only state, check that `R` can reveal metadata without revealing the full chrome, check that metadata never obscures images, verify click-to-rank and keyboard flows, and optionally hand those artifacts to a sub-agent for visual critique.

7. Update `SKILL.md` only for operating-procedure changes.
   - Keep `SKILL.md` concise.
   - Link to references for model matrices and maintenance workflows.
   - Let script `--help` remain the detailed CLI reference.

## When To Use Assets

Add files under `assets/` when the skill needs stable inputs that should travel with the repo:

- a reusable gallery template
- standardized benchmark prompt packs
- seed/reference images safe for redistribution
- masks or layout guides for image editing
- style boards or color palettes used by examples

Do not use `assets/` for:

- generated comparison outputs
- personal or client images unless explicitly intended for the repo
- API responses, manifests, logs, or usage history

If an asset is large or licensing is unclear, keep it in `outputs/` or another ignored local directory and document how to obtain it.
