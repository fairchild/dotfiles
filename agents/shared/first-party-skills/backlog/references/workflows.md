# Workflows

One-shot recipes that aren't part of the daily verb loop — first-time setup in a fresh project, and migration from earlier layouts.

## init (the `/backlog setup` entry point)

Set up `backlog/` in a fresh project. Interactive: ask the operator one question, then scaffold for the chosen backend.

### Step 1 — pick the backend

Ask the operator:

> Which backend? Choose one:
> - **`maildir-git`** — single-worktree project. Everything committed to git; claim is `git mv`. Simplest; the default unless multi-worktree work is expected.
> - **`maildir-shared`** — multi-worktree project (Conductor, parallel `git worktree`). In-flight files live in a git-common-dir shared dir; claim is atomic across worktrees of the clone.
> - **`github-issues`** — tasks live as GitHub Issues; useful when the repo's existing issue queue is already the public work ledger.
> - **`jira`** — tasks live as Jira work items via Atlassian CLI; useful when the team already triages and prioritizes in Jira.
> - **`Custom`** — Create a custom backend.

Default to `maildir-git` if the operator declines to choose. Recommend `maildir-shared` if `git worktree list` shows more than one worktree, or if the project hints at Conductor/cmux use.

### Step 2a — scaffold for `maildir-git`

```bash
mkdir -p backlog/{todo,doing,done}
cat > backlog/AGENTS.md <<'EOF'
# backlog/

`CLAUDE.md` here is a symlink to this file — read one, not both.

Deferred work, one markdown file per task. Location = status:

- `todo/`  — available
- `doing/` — claimed, in flight
- `done/`  — completed (and cancelled — discriminated by the `cancelled` log line)

Use the `backlog` skill (add / advance / progress / cancel / fail / rescue / retry / maintain / status) to interact. There is no backward verb — work that can't proceed is `fail`ed and may be `retry`ed back to `todo/`. Schema and rules: the `backlog` skill's `references/agents-schema.md`.

## Backend

`maildir-git` — everything in this directory is committed to git; claim is `git mv`. See the `backlog` skill's `references/backends/maildir-git.md`.

## Defaults

Frontmatter is optional; recipes apply these defaults when fields are omitted:

- `priority: 999` (low — declare to drive auto-pick ordering)
- `timeout: 7d` (override per-task: shorter for fast agent work, longer for human-paced or human-blocked)
- `dependencies: {}` (declare only hard preconditions)

Override the project default by stating it here (e.g., "default timeout in this project: 24h") and declaring `timeout:` per-task accordingly.

## Pipeline

`todo → doing → done`

The default pipeline. To add intermediate states (e.g. `reviewing/`), create the directory and update this line — `advance` reads it. See the `backlog` skill's `references/pipeline.md`.

## ROADMAP

Strategic counterpart at `backlog/ROADMAP.md` — Intent, Principles, Current Focus, Priorities (named arcs), Non-goals. Tasks optionally link via `arc: <name>` frontmatter. See the `backlog` skill's `references/roadmap.md`.
EOF
ln -s AGENTS.md backlog/CLAUDE.md
```

### Step 2b — scaffold for `maildir-shared`

```bash
mkdir -p backlog/{todo,done}
shared_root="$(git rev-parse --git-common-dir)/backlog"
mkdir -p "${shared_root}/doing"
ln -s "${shared_root}/doing" backlog/doing

# gitignore the symlink so the per-worktree target doesn't appear as untracked
touch .gitignore
grep -qxF "backlog/doing" .gitignore || echo "backlog/doing" >> .gitignore

cat > backlog/AGENTS.md <<'EOF'
# backlog/

`CLAUDE.md` here is a symlink to this file — read one, not both.

Deferred work, one markdown file per task. Location = status:

- `todo/`  — available
- `doing/` — claimed, in flight (symlink into git-common-dir shared dir)
- `done/`  — completed (and cancelled — discriminated by the `cancelled` log line)

Use the `backlog` skill (add / advance / progress / cancel / fail / rescue / retry / maintain / status) to interact. There is no backward verb — work that can't proceed is `fail`ed and may be `retry`ed back to `todo/`. Schema and rules: the `backlog` skill's `references/agents-schema.md`.

## Backend

`maildir-shared` — `todo/`, `done/`, `failed/` are committed to git; in-flight dirs (`doing/`, etc.) live under `$(git rev-parse --git-common-dir)/backlog/`, shared across all worktrees of the clone via gitignored symlinks. Claim is atomic across worktrees. See the `backlog` skill's `references/backends/maildir-shared.md`.

## Defaults

Frontmatter is optional; recipes apply these defaults when fields are omitted:

- `priority: 999` (low — declare to drive auto-pick ordering)
- `timeout: 7d` (override per-task: shorter for fast agent work, longer for human-paced or human-blocked)
- `dependencies: {}` (declare only hard preconditions)

Override the project default by stating it here (e.g., "default timeout in this project: 24h") and declaring `timeout:` per-task accordingly.

## Pipeline

`todo → doing → done`

The default pipeline. To add intermediate states (e.g. `reviewing/`), create the directory and update this line — `advance` reads it. Add the intermediate dir name to `.gitignore` too (mirrors `backlog/doing`). See the `backlog` skill's `references/pipeline.md`.

## ROADMAP

Strategic counterpart at `backlog/ROADMAP.md` — Intent, Principles, Current Focus, Priorities (named arcs), Non-goals. Tasks optionally link via `arc: <name>` frontmatter. See the `backlog` skill's `references/roadmap.md`.
EOF
ln -s AGENTS.md backlog/CLAUDE.md
```

### Step 2c — scaffold for remote backends

Remote backends are configured by `scripts/backlog.sh setup`; do not hand-roll their AGENTS.md from the maildir templates above.

For GitHub Issues:

```bash
skills/backlog/scripts/backlog.sh setup --backend=github-issues
```

For Jira:

```bash
skills/backlog/scripts/backlog.sh setup \
  --backend=jira \
  --project=TEAM \
  --type=Task \
  --label=backlog \
  --status-todo="To Do" \
  --status-doing="In Progress" \
  --status-done="Done" \
  --status-failed="Failed"
```

Jira setup requires Atlassian CLI authentication (`acli jira auth status`) and a project workflow whose statuses already match the configured `## Statuses` mapping. Full setup notes and smoke-test guidance: `backends/jira.md`.

### Step 3 — scaffold ROADMAP.md (both backends)

```bash
[[ -f backlog/ROADMAP.md ]] || cat > backlog/ROADMAP.md <<'EOF'
# ROADMAP

## Intent
<!-- One paragraph. What this project ultimately intends to be. -->

## Principles
<!-- 3–7 short statements. What values guide decisions when tradeoffs come up. -->

## Glossary
<!-- Optional. Only terms with real ambiguity in this project. -->

## Current Focus
<!-- 1–3 paragraphs. The active arc — what we're pushing on, why now,
     what "done with this arc" looks like. -->

## Priorities
<!-- Ordered list of named arcs (kebab-case) with one or two sentences of
     reasoning. Tasks queued under an arc declare `arc: <name>` in frontmatter. -->

## Non-goals
<!-- Things we are explicitly *not* doing right now. -->
EOF
```

For a guided interview that fills the ROADMAP instead of the empty skeleton, load `references/reflect.md` and follow its initialization submode.

`AGENTS.md` is the cross-tool source of truth; `CLAUDE.md` symlinks to it so Claude Code auto-loads the same conventions. Commit everything so collaborators see it. For `maildir-shared` the in-flight files themselves stay out of git (they're in the gitignored symlinked dir) — only the AGENTS.md backend declaration and the `.gitignore` entry land in commits.

## migrate

For a project on the older flat layout (pending items at `backlog/*.md`, completed at `backlog/done/*.md`, possibly with `backlog/done/{YYYY}/` year subdirs from an interim version):

```bash
mkdir -p backlog/todo backlog/doing

# Pending items: anything directly under backlog/ that isn't AGENTS.md/CLAUDE.md/ROADMAP.md
for f in backlog/*.md; do
  base=$(basename "$f")
  case "$base" in AGENTS.md|CLAUDE.md|ROADMAP.md) continue ;; esac
  git mv "$f" "backlog/todo/$base"
done

# Flatten any year subdirs back into backlog/done/
for d in backlog/done/*/; do
  [[ -d "$d" ]] || continue
  for f in "$d"*.md; do
    [[ -f "$f" ]] || continue
    git mv "$f" "backlog/done/$(basename "$f")"
  done
  # Drop the now-empty year (or quarter, or cancelled/) subdir
  rmdir "$d" 2>/dev/null || true
done
```

Review the result with the `status` recipe in `worker.md`, then commit as a single "chore(backlog): migrate to maildir layout" commit. Reversible via `git revert` if anything looks wrong.

## migrate maildir-git → maildir-shared

For projects switching from the default backend to the cross-worktree shared variant — see the full recipe in `backends/maildir-shared.md` under "Migration from maildir-git". Updates `.gitignore`, moves in-flight files into the git-common-dir shared root, creates worktree-local symlinks, updates `backlog/AGENTS.md` to declare `## Backend: maildir-shared`.
