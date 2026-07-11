# Worker Operations

Verb semantics for working tasks in the backlog. `../SKILL.md` covers adding tasks; this doc covers everything else. Pipeline declaration (how `advance` knows where to go): `pipeline.md`. Storage mechanism for each verb (the bash): `backends/<chosen>.md`, where `<chosen>` is whichever backend `backlog/AGENTS.md` declares.

Verb shape is constant across backends. What differs is how each verb *claims*, *appends*, and *moves* — the backend page is where those mechanics live.

## Rules

- **No backward verb.** A task that can't proceed gets `fail`ed (with reason) and may later be `retry`ed back to `todo/`. There is no "release" — pretending the work wasn't tried muddies the log.
- **Spec contradictions surface via `fail`, not silent edit.** If execution shows the task's premise is wrong and no coherent slice can ship under it, `fail` with reason `"premise needs revision: <what's wrong>"`. The `retry` recipe permits the spec edit that lands the corrected premise. (Orthogonal to the slice + follow-up pattern, which applies when a coherent slice shipped on a valid premise — see `worker-loop.md` once it exists.)
- **Frontmatter and description above the divider are frozen after first commit** (one exception: `retry` may edit them, since retry IS a correction).
- **Append after each state transition; commit alongside the move.** That's what keeps `cat` and `git log` synchronized. (For `maildir-shared`, mid-flight `progress` writes don't commit — the in-flight file isn't in any worktree's git tree until it advances to a terminal dir. Boundary transitions still commit.)
- **Single writer per claim.** The first `advance` (todo/ → doing/) is the lock; subsequent advances are by the same claimer. Backends provide the lock mechanism (maildir-git: `git mv` collisions surface at merge; maildir-shared: atomic `O_EXCL` create in the shared dir).
- **Commit before the first advance.** Uncommitted task files can't be claimed — other agents can't see them.
- **Timeout is author-set, never claimer-extended.** Default `7d` if not declared. If the budget is wrong, `fail` with a reason — someone can `retry`.
- **Dependencies are parallel.** Task is takeable when every dep slug resolves under `done/`.

## Worker mode

A well-formed backlog task has its planning baked in — problem, decisions, verification commands, deps — so workers should execute in agent (acceptEdits) mode straight through.

If a worker is dispatched in plan mode, the pattern is:

1. Draft a plan from the task.
2. Exit plan mode with the plan (operator approves).
3. Dispatch a subagent (via the Task tool) in agent mode with the approved plan as its prompt. The subagent executes; the parent reports back.

In the dispatch prompt, the parent adds operational context — cwd, branch, where the in-flight file lives, how to advance after — around the spec, and forwards the spec itself unchanged. Re-summarizing or editorializing the spec creates a second source of truth that drifts from the author's intent; the subagent's job is to execute the spec, not the parent's reading of it.

Plan mode is for work the operator wants to review before execution. Backlog tasks already passed that review at authoring time — the task itself IS the approved plan. The subagent handoff keeps the planning checkpoint where it's load-bearing (the parent) without re-litigating execution.

If you find the task underspecified during execution — filling gaps the author didn't fill — surface that as `fail | reason="needs replanning: ..."` rather than burning the claim. A sharper retry helps the next worker.

## Log line format

```
- {ISO ts} {kind} key=value ... [| free prose]
```

Kinds: `advanced`, `progress`, `cancelled`, `failed`, `rescued`, `retried`.

KV fields grep cleanly (`grep 'branch=feat/foo'`), free prose follows `|`, and long-form detail belongs in the commit body — the bullet is the index, git is the archive (`git show <sha>` retrieves the long form).

The `advanced` line carries `to=<dir>` always. On entry to the in-flight phase (from `todo/`), it also carries `claimer=<id>` and `branch=<name>` — those are the claim. Subsequent advances within the same claim omit them; the latest `advanced to=<in-flight>` or `rescued` line is the claim of record.

## Verbs

Semantics here are constant. Bash is in `backends/<chosen>.md`.

### advance

The one forward verb. Moves a task one step along the pipeline declared in `backlog/AGENTS.md` (default `todo → doing → done`; see `pipeline.md`).

Three phases behave the same way semantically — only the log line differs:

- **Entry** (todo/ → doing/) — the claim. Stamp `claimer=` and `branch=`.
- **Intermediate hop** (e.g. doing/ → reviewing/) — same claimer continues; no re-stamp.
- **Completion** (last in-flight → done/) — the work shipped; PR URL goes in `| PR=<url>` prose. That URL paired with the `advanced to=done` timestamp is the agent-done record later lead-time tracking pairs against the eventual merge. Default-case completions should always carry it; absent only when the spec explicitly said no PR.

**No-slug advance from todo/** ("take the next thing"): glob `todo/`, filter to tasks whose every dep is in `done/`, sort by `priority` (default 999) ascending then oldest mtime, advance the first.

### progress

Append a semantic, idempotent note to the claim's worklog. Does NOT reset the timeout clock — only `advanced` and `rescued` do. Progress notes are for incremental detail; phase markers go in `advanced`.

Write progress notes so the next claimer can skip work already done. "auth migration prototype passing locally" tells the next claimer what's safe to skip; "still working" tells them nothing.

Notes earn their keep when the claim is rescuable or crosses meaningful phase boundaries. Absence of a note on a short single-phase claim isn't a smell — there's nothing for the next claimer to skip.

### cancel

Abandon (any in-flight → `done/`). Requires a reason. The `cancelled` log line discriminates from a normal advance-to-done. Terminal.

### fail

Dead-letter: move any in-flight task to `backlog/failed/` with a reason. Use for anything that didn't complete — out of budget, blocked on external, out-of-scope, spec premise turned out wrong. The reason is the log line; operators may `retry` later.

### rescue

Pick up an in-flight task whose claim has gone stale (timeout exceeded). In-place — no state transition. The staleness check refuses if the existing claim is still active, preventing accidental claim-stealing.

After rescuing, read the file's full log and skip activities prior progress notes already completed. See `parallel-agents.md` for the activity-skipping pattern and the advance-prelude variant that bundles rescue with detection.

### retry

`failed/X.md` → `todo/X.md`. Requires a reason. **Does not work on `done/` tasks** — done is terminal; revisits go in a new task that references the old slug.

**Retry is the one place spec edits are permitted.** Retrying signals "this needs fixing to succeed" — often the spec itself was wrong (priority, timeout, dependencies, or the description's plan). The retry log line captures the why; the git diff captures the what.

A retried task whose dependencies have since moved (e.g., a dep is now in `failed/`) won't be takeable until the dep chain is healthy again. Auto-pick will quietly skip it; retry the deps first if you need them resolved.

### status

Counts per state directory, plus the most-recent in-flight files. A glance at what's where.

### maintain

Advisory walk over the buckets in `maintain.md`; never moves files (one exception: it may fail author-authorized TIMED OUT entries — see `parallel-agents.md`).
