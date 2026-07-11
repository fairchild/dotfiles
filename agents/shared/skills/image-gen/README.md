# image-gen

Human-facing notes for the `image-gen` skill.

This skill is becoming more than a wrapper around image APIs. The direction is a comparison-first image generation workflow: when I ask for an image, the skill should produce candidates from the enabled providers, help me pick the best one with minimal friction, save the full comparison data locally, and return only the winning image to the session that invoked the skill.

## Current Shape

The skill currently includes provider scripts for:

- OpenAI GPT Image
- Google Gemini / Nano Banana
- Google Imagen
- fal.ai FLUX

Each provider script can still be used directly:

```bash
skills/image-gen/scripts/generate_openai.py \
  --prompt "a cat wearing a top hat"
```

The scripts are executable UV scripts. Direct execution is the normal path; `uv run --script skills/image-gen/scripts/<script>.py ...` is still fine as a fallback if executable bits are unavailable.

Provider scripts follow a small adapter protocol so the comparison and review tools can call them without provider-specific code. Each provider script is executable, declares UV/PEP 723 metadata, supports `--prompt`, `--output`, `--output-dir`, `--model`, `--check`, and `--protocol`, records successful generations, and prints the resolved output path as the final stdout line.

The only allowed local helper import is `scripts/common.py`.

For the implemented design and provider protocol approach, read `references/provider-protocol-architecture.html`. For the local storage convention, read `references/storage-policy.md`.

If `--output` is omitted, generated files go under `skills/image-gen/outputs/`. Successful generations are logged to `skills/image-gen/data/generations.jsonl`.

The current comparison runner is `scripts/run_examples.py`. It is meant for fixed example prompts and model benchmarking. It dry-runs by default and only generates images when passed `--generate`. Single-example generated manifests are reviewable with `scripts/review_gallery.py`.

Comparison run directories can be reviewed with `scripts/review_gallery.py`:

```bash
skills/image-gen/scripts/review_gallery.py \
  --run-dir skills/image-gen/outputs/comparisons/20260516-jrnlfish-logos
```

After UI changes or comparison runs, capture the gallery for agent review with
`scripts/evaluate_review_gallery.py`:

```bash
skills/image-gen/scripts/evaluate_review_gallery.py \
  --run-dir skills/image-gen/outputs/comparisons/20260516-jrnlfish-logos
```

The evaluator writes desktop, interaction, and mobile screenshots plus
`layout.json`, `checks.json`, and `notes.md` under
`skills/image-gen/outputs/evaluations/`. Use these artifacts to inspect the
rendered page, catch regressions, and support a future sub-agent or evaluation
loop that judges whether the review page still stays image-first. When invoked
with `--run-dir`, it serves a temporary copy so save and ranking checks do not
mutate the original comparison run.

## Product Direction

The intended normal workflow is:

1. I ask for an image.
2. The skill generates one candidate from each enabled provider script by default.
3. The skill opens a local comparison page.
4. I sort the images directly. The leftmost image is the winner.
5. Optional controls let me add one comment or regenerate one/all candidates.
6. The skill saves the candidates, prompt, models, ranking, winner, and comment.
7. The invoking session receives only the winner path and displays only that image.

The important user experience rule is that ranking should be nearly effortless. The review page should stay image-first: click the left or right side of an image to move it, drag it into place, optionally add one comment, save.

## Why Comparison-First

Image generation quality varies by model, prompt type, and provider. A single provider default hides that variance. Comparing providers by default gives us:

- better immediate output selection
- a growing local record of which models do well on which prompts
- structured preference data for future evaluation or training sets
- less reliance on memory of past results

The comparison work should be private to the skill. The main session should not need to inspect every candidate. It should get the selected winner.

## Data Model

Generated artifacts and feedback stay local and gitignored by default.

```text
skills/image-gen/
├── outputs/
│   └── comparisons/<run-id>/
│       ├── candidates/
│       ├── gallery.html
│       ├── manifest.json
│       ├── feedback.json
│       └── winner.<ext>
│   └── evaluations/<run-id>/<timestamp>/
│       ├── default.png
│       ├── interaction.png
│       ├── mobile.png
│       ├── layout.json
│       ├── checks.json
│       └── notes.md
└── data/
    ├── generations.jsonl
    ├── comparison_runs.jsonl
    └── rankings.jsonl
```

Current implemented history:

- `data/generations.jsonl`: one entry per successful provider generation.
- `data/rankings.jsonl`: one entry per submitted ranking or winner choice.
- `data/regenerations.jsonl`: one entry per review-gallery regeneration event.

Planned comparison history:

- `data/comparison_runs.jsonl`: one entry per comparison request.

Useful fields for future training data:

- prompt
- prompt hash
- provider
- model
- generation parameters
- output path
- image dimensions and file size
- selected winner
- full ranking
- comment

Sensitive prompts can opt out of history logging:

```bash
IMAGE_GEN_DISABLE_HISTORY=1 skills/image-gen/scripts/generate_openai.py ...
```

This is a documented repo-local storage convention, not a general Agent Skills standard. The skill keeps generated files in ignored `outputs/` and local history in ignored `data/` so agents and scripts have stable paths, while `IMAGE_GEN_OUTPUT_DIR`, `IMAGE_GEN_DATA_DIR`, and `IMAGE_GEN_DISABLE_HISTORY` provide privacy and relocation controls. See `references/storage-policy.md`.

## Comparison UI

The review UI optimizes for speed.

Default visible controls:

- image grid where order is the ranking
- click images in preferred order: first click becomes rank 1, second distinct click becomes rank 2, and so on
- drag and drop to reorder
- rank labels and per-image footer actions hidden until hover or direct footer-control focus, and positioned outside the image
- left/right arrow keys move focus; up/down arrow keys promote or demote the focused image
- save button
- `S` keyboard shortcut for saving when focus is outside the comment field
- compact saved/unsaved visual indicator
- reload files button for re-reading manifest, image files, and saved feedback from disk
- reveal details button for showing provider/model names only when wanted
- `R` keyboard shortcut for revealing or hiding provider/model details, even while the rest of the chrome stays hidden
- regenerate one image
- regenerate all images

Optional controls:

- tap/click outside the image cards to reveal prompt, actions, status, and comment
- tap/click empty space again to hide prompt, actions, status, and comment
- `Esc` hides prompt, actions, status, comment, and metadata again
- one comment field

The first submission path should be image-only. On page open, show only the images. Provider/model details are hidden by default to reduce bias. Metadata must never cover the image being judged. The leftmost image is the winner, and the full visible order is the ranking. Comment is useful but optional.

Click-to-rank interaction: first distinct image clicked becomes rank 1, the second becomes rank 2, the third becomes rank 3, and any remaining unclicked images follow in their current order. If the user clicks an already-ranked image or clicks again after completing a pass, that click starts a fresh ranking pass with that image as rank 1; subsequent distinct clicks fill rank 2, rank 3, and so on until saved.

The current local review server saves `feedback.json` in the comparison run directory and appends ranking entries to `data/rankings.jsonl`. It also copies the selected image to `winner.<ext>`. Regeneration updates the manifest to point at the newest candidate and appends local regeneration events to `data/regenerations.jsonl`.

## Scripts

Current scripts:

- `scripts/generate_openai.py`: OpenAI GPT Image generation.
- `scripts/generate_gemini.py`: Gemini / Nano Banana generation.
- `scripts/generate_imagen.py`: Imagen generation.
- `scripts/generate_fal.py`: fal.ai generation.
- `scripts/check_protocol.py`: no-key provider adapter protocol checker.
- `scripts/run_examples.py`: fixed example comparisons for current model presets.
- `scripts/review_gallery.py`: local review server for choosing, ranking, commenting, and regenerating comparison outputs.
- `scripts/evaluate_review_gallery.py`: Playwright capture and checks for review gallery screenshots, image loading, metadata placement, click-to-rank, and keyboard behavior.
- `scripts/common.py`: shared env loading, output path handling, MIME/extension handling, and history logging.

Likely next script:

- `scripts/compare_prompt.py`: normal comparison-first workflow for arbitrary prompts. It should generate from enabled providers, launch `review_gallery.py`, persist feedback, and print only the winning image path.

## Directory Boundaries

- `outputs/`: generated images, comparison galleries, manifests, and local run artifacts. Ignored by git.
- `data/`: local JSONL history and preference data. Ignored by git.
- `references/`: tracked docs for model matrices, maintenance workflow, and design decisions.
- `assets/`: tracked reusable inputs such as gallery templates, prompt packs, safe reference images, masks, style boards, or CSS/JS used by the review UI.

Do not store routine generated images in `assets/`. Generated images belong in `outputs/`.

## Maintenance

Image APIs and model names drift quickly. The maintenance workflow is:

1. Check official provider docs.
2. Update `references/current-models.md`.
3. Update provider scripts and `scripts/run_examples.py`.
4. Run free verification:

```bash
skills/image-gen/scripts/check_protocol.py
skills/image-gen/tests/test_image_gen.py
skills/image-gen/scripts/run_examples.py --list
skills/image-gen/scripts/run_examples.py
```

The focused protocol checker is also wired into PR validation for changes under `skills/image-gen/`, so adapter breakage is caught before merge without provider keys or paid generation.

5. Run paid comparisons only when useful.
6. Keep `SKILL.md` compact. Put human explanation here and operational details in `references/`.

See also:

- `SKILL.md`
- `references/current-models.md`
- `references/maintenance-workflow.md`
- `references/provider-protocol-architecture.html`
- `references/storage-policy.md`
- `outputs/README.md`
- `data/README.md`
- `assets/README.md`
