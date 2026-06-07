---
description: Clone a repo into ~/code/github/<owner>/<repo>, inspect it, and recommend the best next step
---
Clone and evaluate the repository at $1.
If additional arguments are provided beyond the URL, treat `${@:2}` as the evaluation focus and prioritize findings relevant to that focus.

Use this repository location convention:

- GitHub repos: `~/code/github/<owner>/<repo>`
- If needed later for other hosts: `~/code/git/<host>/<owner>/<repo>`
- Temporary evaluations: `~/code/tmp/<owner>-<repo>`

Procedure:

1. Parse the repository host, owner, and repo name from `$1`.
2. If this is a GitHub repo, use the conventional destination `~/code/github/<owner>/<repo>`.
3. If the destination parent directory does not exist, create it.
4. If the repo is not already present locally, clone it there.
5. If it already exists locally, do not reclone. Instead:
   - report the existing path
   - inspect the current checkout
   - fetch remote state if useful for review, but do not change branches unless asked
6. Inspect the repo before proposing work:
   - `README*`
   - `AGENTS.md` / `CLAUDE.md`
   - package/runtime files (`package.json`, `bun.lock`, `pnpm-lock.yaml`, `uv.lock`, etc.)
   - top-level structure
   - docs and examples
   - recent git activity and current status
7. Then summarize:
   - what the repo is
   - stack and architecture
   - apparent maturity/maintenance status
   - how relevant it is to my pi workflow
   - risks, caveats, or signs of staleness
   - if this is a catalog, awesome list, or index repo, extract the most relevant entries for my workflow
8. Finally recommend the most useful next actions:
   - give 3–5 ranked suggestions
   - clearly identify the single highest-leverage thing to do next
   - prefer actions that help me adopt, evaluate, or integrate the repo

Constraints:

- Be conservative.
- Do not install dependencies, edit files, or make commits unless I explicitly ask.
- Show the final local path clearly.
- If the repo contains pi-specific docs, skills, prompts, extensions, or packages, call those out explicitly.
