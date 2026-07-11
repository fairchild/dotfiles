# Image Generation Outputs

Generated comparison images and manifests are written here by default.

This directory is intentionally gitignored except for this README. Scripts use it as the stable default output root unless `IMAGE_GEN_OUTPUT_DIR` or `--output-dir` points somewhere else. Local metadata about generated files is recorded separately in `../data/generations.jsonl`.

Suggested layout:

```text
outputs/
├── examples/<timestamp>/      # comparison runner output, reviewable for single examples
├── test-runs/<timestamp>/     # paid test generation output
└── generated-*.png            # one-off script output when --output is omitted
```
