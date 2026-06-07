# Image Generation History

Provider scripts append local usage history here by default.

Tracked file:

- `README.md`

Ignored local files:

- `generations.jsonl` - one JSON object per successful generated image
- `rankings.jsonl` - saved review-gallery rankings, winner choices, and comments
- `regenerations.jsonl` - review-gallery regeneration events
- future local indexes or reports built from `generations.jsonl`

Each history entry records the provider, model, prompt, prompt hash, output path, file size, detected dimensions when available, and non-secret generation parameters.

Set `IMAGE_GEN_DISABLE_HISTORY=1` for sensitive prompts that should not be logged. Set `IMAGE_GEN_DATA_DIR=/path/to/dir` to move the local history outside the skill directory.
