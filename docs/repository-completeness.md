# Repository completeness

The whitelist `.gitignore` prevents accidental publication, but an intended file can be created successfully and still remain invisible to Git. The completeness check treats that as a failure before review.

## Contract and derived references

[`../scripts/public-entrypoints.txt`](../scripts/public-entrypoints.txt) lists the small set of load-bearing public files. The checker also derives local requirements from:

- relative Markdown links in README, ROADMAP, `docs/*.md`, and the shared-agent README;
- `./scripts/...` task commands in `.mise.toml`;
- direct `$DOTFILES_DIR/scripts/...` executable references in tracked shell scripts.

External URLs, anchors, absolute/private paths, generated runtime, and ordinary prose are not interpreted as repository files.

## Local use

```sh
mise run check:completeness
mise run test:completeness
```

Doctor runs the same check, and the public-safety workflow runs both the real-tree check and historical omission fixtures.

## Adding a public path intentionally

1. Add the file or directory exception to the root `.gitignore` if its parent is not already public.
2. Add the file with `git add <path>` and confirm `git ls-files --error-unmatch <path>` succeeds.
3. If the path is a load-bearing entrypoint, add it to `scripts/public-entrypoints.txt` with a short reason.
4. Run `git check-ignore -v --no-index <path>`; a public path must not resolve to an ignore rule.
5. Run the completeness and public-safety checks before committing.

The diagnostic includes the responsible ignore rule when a required path is ignored, which is the part ordinary file-writing tools and `git status` can hide.
