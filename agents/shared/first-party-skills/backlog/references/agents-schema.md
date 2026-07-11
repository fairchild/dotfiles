# Backlog Schema

Canonical spec for backlog file structure, frontmatter, and body format. The recipes in `../SKILL.md` (add) and `worker.md` (everything else) implement this; if there's a conflict between the recipes and this doc, the recipes win and this doc needs updating.

## Directory Layout

```
backlog/
  AGENTS.md     # convention pointer + optional Pipeline declaration
  inbox/        # optional triage queue, not claimable until advanced to todo
  todo/         # available
  doing/        # claimed, in flight (the default in-flight dir)
  reviewing/    # (optional) intermediate in-flight; created if the project's pipeline includes it
  done/         # completed (and cancelled, discriminated by log line)
  failed/       # dead-letter for tasks that couldn't proceed (created on demand)
```

The pipeline defaults to `todo → doing → done`. A project may declare a longer pipeline (e.g. `todo → doing → reviewing → done`) or an intake stage before `todo` (e.g. `inbox → todo → doing → done`) in `backlog/AGENTS.md`. See `pipeline.md`.

Flat `done/` — no time partitioning. If it grows large enough to be annoying (years from now), operators can shard by hand; nothing migrates automatically and no recipe relies on the directory shape.

`failed/` is created on demand by the `fail` recipe; it doesn't exist until the first failure. Operators review it manually and either `retry` (back to todo/) or leave it as terminal history.

**In-flight dirs**, by convention, are pipeline stages after `todo/` and before `done/`. `inbox/`, `todo/`, `done/`, and `failed/` are not in-flight. Recipes that need "all currently-claimed work" enumerate via this exclusion. `failed/` is out-of-pipeline and never visited by `advance`.

## Filename

`{task-name}-{category}.md`

- `task-name` — kebab-case
- `category` — one of `plan`, `followup`, `task-list`, `ideas`

Examples:

- `docs-r2-storage-plan.md`
- `session-cache-followups-task-list.md`
- `chronicle-extractor-quality-ideas.md`

Slug = filename minus path and `.md`. Dependencies reference tasks by slug; the agent resolves a slug by walking `todo/`, `doing/`, `done/`, and `failed/` (if present).

## Frontmatter (optional)

YAML between two `---` lines at the top of the file. **Every field has a default**, so a minimal task can omit frontmatter entirely. Author-set at creation and frozen after first commit, with one exception: `retry` may edit frontmatter to correct issues found during the prior attempt (see `worker.md`'s retry recipe).

```yaml
---
priority: 2                      # 1 = highest. Default: 999 (sorts after every declared priority)
timeout: 3d                      # humanish: 4h, 3d, 2w. Default: 7d
dependencies:                    # map of slug → reason. Default: empty (no deps)
  schema-migration: "needs new claim block format"
---
```

A minimal task with no frontmatter at all is valid:

```markdown
# Quick fix

The login button is misaligned on mobile.

---
```

This gets `priority=999`, `timeout=7d`, `dependencies={}`. Recipes treat it like any other task.

### Defaults and when to override

- **`priority` defaults to `999`** — sorts after every declared priority. Declare a number (1 = highest) when scheduling order matters. With few tasks the default is fine; with many in `todo/`, declare for clarity.
- **`timeout` defaults to `7d`** — long enough for most knowledge work, short enough that a dead claim doesn't linger. Use shorter (`4h`, `1d`) for automated agent tasks; longer (`2w`, `1m`) for tasks needing synchronous human input or external dependencies. Projects with a fundamentally different rhythm can state their convention in `backlog/AGENTS.md`; the recipes still use `7d` as the hardcoded fallback but humans and agents adjust per-task accordingly.
- **`dependencies` defaults to empty** — declare only hard preconditions (the task literally cannot start without X done). Soft "would be nice if X were done first" preferences belong in priority ordering, not deps.

### Dependency validation

Projects may opt into pre-commit dependency validation with the local `backlog-dep-validation` hook. When enabled in the repo's hook config, commits touching `backlog/**/*.md` are rejected if any declared `dependencies:` slug does not resolve to a file under `backlog/`, including dependency files staged in the same commit. The hook validates slug existence only; it does not validate reason text or detect dependency cycles. If it fails, author the missing dependency task with `bash ~/.claude/skills/backlog/scripts/backlog.sh add <slug> [followup|plan|task-list|ideas]`, then recommit.

### Other fields

Additional keys an author writes are preserved in the file but not interpreted by any recipe. Useful for ad-hoc project metadata (`assignee:`, `epic:`, etc.) your project's own workflows might read.

One convention worth naming: **`arc: <kebab-case-name>`** — a single scalar (one arc per task) linking a task to a named arc in `backlog/ROADMAP.md`'s Priorities section (see `references/roadmap.md`). Recipes preserve it but don't act on it; query via `grep -l '^arc: my-arc' backlog/{todo,doing,done}/*.md`.

### Triage integration (optional)

Projects that cooperate with external triage skills (e.g. Matt Pocock's `triage`/`to-issues`/`to-prd`) can layer triage sub-state onto pipeline location using named frontmatter keys. The field's *presence* indicates the sub-state; its *value* carries the actionable context that the triage skill would otherwise put in a label-time comment.

- **`kind: bug | enhancement`** — category role.
- **`needs-info: <what's missing — specific questions>`** — only meaningful on items in the triage-queue dir (e.g. `inbox/` if the pipeline declares one).
- **`ready-for-human: <what kind of human work is needed>`** — only meaningful on items in the claim-ready dir (`todo/`). Absence means the default sub-state (ready-for-agent).
- **`out-of-scope: <reason or .out-of-scope/<slug>.md link>`** — set when a wontfix-enhancement is `fail`ed, recording institutional memory durably alongside the `failed` log line.

Recipes preserve these fields without acting on them — the skill code doesn't change. Each project should declare its convention in `backlog/AGENTS.md` so triage skills and operators agree on the mapping. Sample mapping for a project that extends the pipeline with an `inbox/` stage: `docs/agents/triage-labels.md` in this repo.

## Body

Two halves, divided by a `---` line with blank lines on either side (so markdown renders it as a horizontal rule):

```markdown
# Title

[description: problem, decisions, phases, references, acceptance criteria]

---

- 2026-05-16T14:22:00Z advanced to=doing claimer=conductor:austin-v3 branch=feat/foo
- 2026-05-16T16:45:00Z progress | auth prototype passing locally
- 2026-05-17T11:03:00Z advanced to=done | PR=https://github.com/.../pull/123
```

**Above the divider** is the author-set description, frozen after first commit *except at retry*. Retry permits spec edits because retry IS a correction (see the retry recipe in `worker.md`). Otherwise, state changes go to the log below, not to the description.

**Below the divider** is the append-only event log. Each line is one event.

### Log line format

```
- {ISO timestamp} {kind} key=value ... [| free prose]
```

Strictly one line per event. Long-form detail belongs in the commit body — `git show <sha>` retrieves it. The bullet is the index; git is the archive.

Kinds and their KV / prose conventions:

| kind        | written by | KV fields                                    | prose after `|`         |
|-------------|------------|----------------------------------------------|-------------------------|
| `advanced`  | advance    | `to=<dir>`; `claimer=...` `branch=...` on entry from todo/ | `PR=<url>` on completion (optional) |
| `progress`  | progress   | none                                         | the note                |
| `cancelled` | cancel     | none                                         | the reason              |
| `failed`    | fail       | none                                         | the reason              |
| `rescued`   | rescue     | `claimer=...`, `branch=...`                  | rare                    |
| `retried`   | retry      | none                                         | the reason              |

The `advanced` kind carries `to=<dir>` always. On entry to the in-flight phase (the claim moment, advancing out of `todo/`), it also carries `claimer=` and `branch=`. Subsequent advances within the same claim omit those — the most recent `advanced to=<in-flight>` or `rescued` line is the claim of record.

### Reading state from the log

| Question                    | How to answer                                                              |
|-----------------------------|----------------------------------------------------------------------------|
| Is X claimed?               | Is `X.md` in an in-flight dir with a live (non-stale) claim?               |
| Where is X in the pipeline? | The dir it's in. The most recent `advanced to=<dir>` says how it got there. |
| Who claims X?               | `grep -oE 'claimer=[^ ]+' X.md \| tail -1 \| cut -d= -f2`                  |
| What branch?                | `grep -oE 'branch=[^ ]+' X.md \| tail -1 \| cut -d= -f2`                   |
| How old is the claim?       | Timestamp of the most recent `advanced` or `rescued` line                  |
| How many rescue attempts?   | `grep -c '^- .*rescued' X.md`                                              |
| What's the PR?              | `grep -oE 'PR=[^ ]+' X.md \| tail -1 \| cut -d= -f2-`                      |
| Did it complete?            | `grep -q '^- .*advanced to=done' X.md` (and the file is in `done/`)        |
| Was it cancelled?           | `grep -q '^- .*cancelled' X.md` (file in `done/`; the log discriminates)   |
| Was it dead-lettered?       | Is `backlog/failed/X.md` a regular file?                                   |
| Full history with context   | `git log --follow -- backlog/.../X.md` (traces across the maildir renames) |

Cat shows the story in place; `git log` shows the same events with author and ancestry. They stay synchronized because every recipe both appends one bullet AND commits.

### Single-writer rule

Between the first `advance` (out of `todo/`) and the final exit (advance to `done/`, or `cancel`, or `fail`), only the claiming agent appends. Enforcement is social — the maildir `git mv` is the actual lock. Two agents writing in parallel branches collide at merge, which is the correct failure.
