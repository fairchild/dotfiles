---
name: backlog
description: Markdown task backlog and project roadmap (backlog/{todo,doing,done,failed}/, backlog/ROADMAP.md) for adding, advancing, recording progress, rescuing, cancelling, retrying, failing, maintenance, or reflecting on backlog priorities and roadmap direction.
license: Apache-2.0
---

# Backlog

A task tracker shaped like a maildir. Each task is one markdown file; its directory is its state. Tasks move forward through a pipeline of directories; there is no backward verb.

- `backlog/todo/`   — available to claim
- `backlog/doing/`  — claimed, in flight
- `backlog/done/`   — completed (and cancelled — the log line discriminates)
- `backlog/failed/` — dead-letter for tasks that couldn't proceed (created on demand)

The default pipeline is `todo → doing → done`. A project may add intermediate in-flight directories (e.g. `reviewing/`) by declaring the pipeline in `backlog/AGENTS.md`. See `references/pipeline.md`.

To claim is to advance from `todo/` to the first in-flight dir. The backend declared by `backlog/AGENTS.md` provides the lock mechanism — `maildir-git` lets racing `git mv`s collide at merge; `maildir-shared` uses an atomic create in a git-common-dir shared directory so the race is caught at claim time across worktrees.

## Slash invocation

Invokable as `/backlog <subcommand> [args]`. The canonical mechanism is `scripts/backlog.sh` — it reads `backlog/AGENTS.md`, detects the backend, and dispatches. Agents should prefer the script over re-implementing bash inline.

| Subcommand | Script call | Semantics |
|---|---|---|
| `/backlog setup` | `scripts/backlog.sh setup --backend=<maildir-git\|maildir-shared\|github-issues\|jira>` | One-time scaffold: for maildir backends, creates dirs, AGENTS.md, ROADMAP skeleton, symlinks + .gitignore for `maildir-shared`; for `github-issues`, creates static labels on the remote; for `jira`, writes the Jira project/JQL/status mapping expected by the Atlassian CLI adapter. Remote backends write AGENTS.md + ROADMAP skeleton (no local task tree). Backend flag is **required** — the script refuses without it and prints a heuristic hint based on `git worktree list`. |
| `/backlog add <slug> [category]` | `scripts/backlog.sh add <slug> [category]` | Create new task in `todo/` |
| `/backlog take [slug]` | `scripts/backlog.sh take [slug]` | Claim from `todo/` (auto-pick if no slug) |
| `/backlog advance <slug>` | `scripts/backlog.sh advance <slug>` | One forward step along the pipeline |
| `/backlog progress <note>` | `scripts/backlog.sh progress "<note>"` | Append a progress line to the current claim |
| `/backlog cancel <slug> <reason>` | `scripts/backlog.sh cancel <slug> "<reason>"` | Abandon an in-flight task |
| `/backlog fail <slug> <reason>` | `scripts/backlog.sh fail <slug> "<reason>"` | Dead-letter an in-flight task |
| `/backlog rescue <slug>` | `scripts/backlog.sh rescue <slug>` | Take over a stale claim |
| `/backlog retry <slug> <reason>` | `scripts/backlog.sh retry <slug> "<reason>"` | Move from `failed/` back to `todo/` |
| `/backlog status` | `scripts/backlog.sh status` | Counts per state + recent in-flight |
| `/backlog maintain` | read `references/maintain.md` | Advisory walk over buckets (agent-judgment, no script) |
| `/backlog worker` | follow `references/worker-loop.md` | Full loop: load + maintain + rank + claim + execute + close |
| `/backlog` (no args) | — | Skill loads; agent infers intent from conversation context |

The full script path from a deployed dotclaude is `~/.claude/skills/backlog/scripts/backlog.sh`. Semantics for each verb live in `references/worker.md`; mechanism details (what the script actually does) live in `references/backends/<name>.md`. The test harness `scripts/test.sh` exercises the maildir backends end-to-end including a real `git worktree`-based race test, and syntax-checks every bundled script.

## File shape

Above the divider: what the author meant. Below: what the workers did.

Two halves, divided by `---` with blank lines around it so markdown renders it as a horizontal rule.

```markdown
---
priority: 2
dependencies:
  other-task-slug: "why we depend on it"
---

# Task Title

[problem statement, key decisions, phases, acceptance criteria]

---

- 2026-05-16T14:22:00Z advanced to=doing claimer=conductor:austin-v3 branch=feat/foo
- 2026-05-16T16:45:00Z progress | auth prototype passing locally
- 2026-05-17T11:03:00Z advanced to=done | PR=https://github.com/.../pull/123
```

Frontmatter and description above the divider are author-set and frozen after first commit (one exception: `retry` may edit them, since retry IS a correction). Below the divider is an append-only event log written by workers — see `references/worker.md` for the verb recipes that maintain it.

## Frontmatter (optional)

Every field has a default, so a minimal task can omit frontmatter entirely:

```markdown
# Quick fix

The login button is misaligned on mobile.

---
```

Defaults: `priority=999`, `timeout=7d`, `dependencies={}`. Add fields above the title to override.

- **`priority`** — integer, 1 = highest. Default `999` (sorts after every declared priority). Declare a number when scheduling order matters.
- **`timeout`** — humanish: `4h`, `3d`, `2w`. Default `7d`. Clock anchors to the most recent `advanced` or `rescued` log line — each forward step gets its own stage budget under the same number. Use shorter for automated agent tasks; longer for tasks needing synchronous human input or external dependencies. Project-wide defaults can be stated in `backlog/AGENTS.md`.
- **`dependencies`** — map of slug → reason. Default empty. Declare only hard preconditions; a task is takeable when every dep slug resolves to a file under `done/`.

Additional keys an author writes are preserved but not interpreted by any recipe. Full schema, kinds table, and "reading state" queries: `references/agents-schema.md`.

## Add a task

Gather **slug** (kebab-case), **category** (`plan` / `followup` / `task-list` / `ideas`, filename suffix), and a description.

```bash
scripts/backlog.sh add <slug> [category]
# then edit backlog/todo/<slug>-<category>.md to fill in
# frontmatter (priority/timeout/dependencies) and the body
```

The script writes a skeleton file in `backlog/todo/` and commits with `add(<slug>-<category>)`. Edit the file in-place to fill in the spec (frontmatter + description); follow-up commits to the same file before claim are fine.

Quality: write enough that a fresh session can execute without ever having met you — specific paths, verification commands, deps declared if any. Commit before anyone can claim.

Outcome contract: by default, a claim ends with the worker opening a *merge-ready* PR — the user clicks, reviews, merges. The task is agent-done when its file lands in `done/` with an `advanced to=done | PR=<url>` log line; the human's merge closes the loop. Lead time from agent-done to merged is later trackable from that timestamp. If the task wants something else (draft PR for exploratory work, no PR for batched grooming, etc.), say so in the spec — the default is review-ready.

## Working the backlog

For advance, progress, cancel, fail, rescue, retry, status, and maintain — the verb semantics plus the rules workers must follow — see `references/worker.md`. The canonical implementation lives in `scripts/` (invoke `scripts/backlog.sh <verb>`); the backend declaration in `backlog/AGENTS.md` selects which implementation runs. Mechanism prose for each backend: `references/backends/<name>.md`. For extending the pipeline with intermediate dirs (e.g. `reviewing/`) and how `advance` reads the ordering, see `references/pipeline.md`.

## Roadmap and reflection

`backlog/ROADMAP.md` sits above the queue — Intent, Principles, Current Focus, Priorities (named arcs), Non-goals — and answers *why these tasks, in this order*. Tasks optionally link via `arc:` frontmatter. Shape and conventions: `references/roadmap.md`. For reflecting on the backlog, adding to the roadmap, or initializing one, load `references/reflect.md` and follow its posture.

## References

- `scripts/backlog.sh` — canonical dispatch entrypoint; reads `backlog/AGENTS.md` to detect backend
- `scripts/lib.sh` — shared helpers (pipeline parser, timeout parser, claimer detection, divider resilience)
- `scripts/backlog-maildir-git.sh` — maildir-git implementation
- `scripts/backlog-maildir-shared.sh` — maildir-shared implementation
- `scripts/backlog-github-issues.sh` — github-issues implementation
- `scripts/backlog-jira.sh` — Jira implementation over Atlassian CLI (`acli`)
- `scripts/test.sh` — full verb cycle + cross-worktree race harness on temp repos (maildir backends only — remote backend integration tests are followups)
- `references/worker.md` — verb semantics for workers (advance, progress, cancel, fail, rescue, retry, status, maintain)
- `references/worker-loop.md` — canonical `/backlog worker` recipe (load, maintain, rank, claim, execute, close, report)
- `references/backends/maildir-git.md` — default backend; mechanism docs for git-tracked maildir
- `references/backends/maildir-shared.md` — multi-worktree backend; mechanism docs for git-common-dir shared dir
- `references/backends/github-issues.md` — cross-machine backend; mechanism docs for `gh issue`-backed storage
- `references/backends/jira.md` — cross-machine backend; mechanism docs for Jira work item-backed storage via `acli`
- `references/pipeline.md` — declaring the pipeline; how `advance` knows where to go; conventions for intermediate dirs
- `references/agents-schema.md` — frontmatter schema, log line format, kinds table, reading-state queries
- `references/parallel-agents.md` — distributed-systems patterns and design rationale
- `references/workflows.md` — `init` (first-time setup) and `migrate` (from earlier layouts)
- `references/maintain.md` — advisory walk buckets (mechanical maintenance)
- `references/roadmap.md` — `backlog/ROADMAP.md` shape and the `arc:` linkage convention
- `references/reflect.md` — critical-collaborative planning posture for reflecting on the backlog or editing the roadmap
- `references/README.md` — background, design philosophy, related projects
