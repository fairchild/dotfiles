# Backend: maildir-shared

Storage mechanism for projects whose `backlog/AGENTS.md` declares `## Backend: maildir-shared`. Built for multi-worktree work — Conductor, parallel `git worktree`, anywhere two agents might claim the same task on different branches and not collide until merge.

Verb semantics: `../worker.md`. The canonical implementation is `../../scripts/backlog-maildir-shared.sh` (invoke via `../../scripts/backlog.sh <verb>`). This doc describes the mechanism — for bash, read the script.

## When to pick this backend

- Multi-worktree project where agents work in parallel on different branches.
- Cross-worktree race ("two workers claim the same task on separate branches") would cost meaningful wasted work.
- You want `ls backlog/doing/` to reflect *every* in-flight task on this clone, not just on this branch.

For one-worktree-at-a-time projects, `maildir-git` is simpler.

## Mental model

Git tracks *history truth* — the queue (`todo/`), completed work (`done/`), dead-letters (`failed/`). Those stay in the worktree, committed.

The git-common-dir tracks *coordination truth* — what's actively claimed right now. In-flight dirs live at `$(git rev-parse --git-common-dir)/backlog/`, shared across every worktree of the clone. The shared dir IS the lock register: a file exists there iff someone has claimed the task.

The worktree restores `ls backlog/doing/` inspectability via a symlink to the shared dir. The symlink is gitignored, auto-created on demand, and resolves to the same shared location from every worktree.

## Layout

```
worktree (git-tracked):           shared (git-common-dir):
backlog/                          $(common-dir)/backlog/
  todo/        committed            doing/       in-flight files
  done/        committed            reviewing/   (if pipeline declares)
  failed/      committed
  doing/       → symlink to shared/doing
  reviewing/   → symlink to shared/reviewing
  AGENTS.md    committed
  CLAUDE.md    → AGENTS.md
  ROADMAP.md   committed
```

`.gitignore` excludes the symlinks (one line per in-flight dir name):

```
backlog/doing
backlog/reviewing
```

## How each verb interacts with the two locations

| Verb | Reads | Writes | Commits? |
|---|---|---|---|
| `add` | — | worktree `todo/` | yes |
| `take` / `advance` from `todo/` | worktree `todo/` + shared in-flight | shared in-flight (O_EXCL); worktree `git rm` of todo | yes (the `git rm`) |
| `progress` | shared in-flight file | append to shared file | no — file isn't in any tree |
| `advance` intermediate (e.g. `doing/` → `reviewing/`) | shared | shared | no |
| `advance` to `done/` | shared | worktree `done/` | yes |
| `cancel` / `fail` | shared | worktree `done/` or `failed/` | yes |
| `rescue` | shared | append to shared file | no |
| `retry` | worktree `failed/` | worktree `todo/` | yes |

The pattern: anything that touches a terminal dir (`done/`, `failed/`, back to `todo/`) commits because the file is in git. Anything mid-flight in shared doesn't commit because the file isn't tracked by any branch.

## The two mechanisms worth seeing inline

The script does both; these are the load-bearing bits the rest of the doc references.

### Atomic claim via `O_EXCL`

Two worktrees racing for the same slug both attempt to create the same shared file. The kernel admits exactly one; the loser sees a redirect failure under noclobber.

```bash
if ! ( set -o noclobber; cat "$src" > "$shared_dst" ) 2>/dev/null; then
  echo "claim conflict: $slug already in flight" >&2; exit 1
fi
```

No separate lockfile — the file IS the lock.

### Symlink self-healing prelude

Every verb begins by ensuring the worktree-local symlinks resolve. New worktrees self-heal on first invocation; manual deletions get repaired.

```bash
for d in $(backlog_inflight_dirs); do
  shared="$(git rev-parse --git-common-dir)/backlog/${d}"
  link="backlog/${d}"
  mkdir -p "$shared"
  [[ -L "$link" ]] || { rm -rf "$link" 2>/dev/null; ln -s "$shared" "$link"; }
done
```

`backlog_inflight_dirs` is in `../../scripts/lib.sh` — reads the project's `## Pipeline` line, returns every dir name that isn't `todo` or `done` (defaulting to `doing` if no pipeline declared).

## Maintain additions

The buckets in `../maintain.md` apply unchanged for `maildir-shared` — `find backlog/{doing,reviewing,...}/` traverses through the symlinks. One backend-specific bucket worth surfacing:

### `ORPHANED SHARED IN-FLIGHT`

A file in a shared in-flight dir whose claim branch no longer exists (locally or on a remote). Indicates a worktree was deleted mid-claim. Surface for operator decision: `fail` (most likely) or `rescue` if the work is still desired.

The script doesn't enumerate this — maintain is advisory and benefits from agent judgment. The check, if you wanted to script it:

```bash
existing=$(git branch --list --all --format='%(refname:short)' | sort -u)
for f in "$(git rev-parse --git-common-dir)/backlog"/*/*.md; do
  branch=$(grep -oE 'branch=[^ ]+' "$f" | tail -1 | cut -d= -f2)
  [[ -n "$branch" ]] && ! grep -qx "$branch\|origin/$branch" <<<"$existing" \
    && echo "ORPHANED: $f (branch=$branch gone)"
done
```

## Migration from maildir-git

Run on a single worktree of the clone. Moves any in-flight files into the shared dir, adds `.gitignore` entries, creates symlinks, switches the `## Backend` declaration.

```bash
common_dir=$(git rev-parse --git-common-dir)
shared="$common_dir/backlog"
mkdir -p "$shared/doing"

# Move any in-flight files (often empty). Portable across BSD/GNU find.
for path in backlog/*/; do
  d=$(basename "${path%/}")
  case "$d" in todo|done|failed) continue ;; esac
  mkdir -p "$shared/$d"
  for f in "backlog/$d"/*.md; do
    [[ -f "$f" ]] || continue
    git rm "$f" && mv "$f" "$shared/$d/$(basename "$f")"
  done
  rm -rf "backlog/$d"
  ln -s "$shared/$d" "backlog/$d"
  grep -qxF "backlog/$d" .gitignore || echo "backlog/$d" >> .gitignore
done

# Edit backlog/AGENTS.md to declare ## Backend: maildir-shared (manual or sed)
git add .gitignore backlog/AGENTS.md
git commit -m "chore(backlog): migrate to maildir-shared backend"
```

Reversible via `git revert` for the metadata changes, then move files back from the shared dir.

## Race semantics

The O_EXCL create is the lock. Two agents simultaneously calling `take` for the same slug both attempt `cat > "$shared"` with noclobber set; the kernel admits exactly one. The loser sees a "claim conflict" message and exits non-zero. The file IS the lock — no separate lockfile, no register to keep in sync.

When the work completes (`done`, `cancel`, or `fail`), the file leaves the shared dir; the slug becomes claimable again only via `retry` from `failed/` (since `done/` is terminal).

Cross-machine coordination is *not* handled — the shared dir lives in one clone's `.git/`. A different machine's clone has a different common-dir and won't see this clone's claims. For cross-machine, see `github-issues.md`.
