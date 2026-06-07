#!/usr/bin/env bash
# maildir-shared backend — todo/done committed to git; in-flight dirs live in
# $(git rev-parse --git-common-dir)/backlog/, shared across all worktrees of
# the clone. Claim is atomic via O_EXCL create.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
. "$script_dir/lib.sh"

shared_root="$(git rev-parse --git-common-dir 2>/dev/null)/backlog"

ensure_symlinks() {
  mkdir -p "$shared_root"
  local d shared link
  for d in $(backlog_inflight_dirs); do
    shared="${shared_root}/${d}"
    link="backlog/${d}"
    mkdir -p "$shared"
    if [[ ! -L "$link" ]]; then
      rm -rf "$link" 2>/dev/null || true
      ln -s "$shared" "$link"
    fi
  done
}

find_shared() {
  local slug="$1"
  local d
  for d in "${shared_root}"/*/; do
    if [[ -f "${d}${slug}.md" ]]; then
      echo "${d}${slug}.md"
      return 0
    fi
  done
  return 1
}

cmd_setup() {
  [[ -f backlog/AGENTS.md ]] && { echo "backlog/AGENTS.md exists — refusing to overwrite" >&2; exit 1; }
  mkdir -p backlog/{todo,done}
  mkdir -p "${shared_root}/doing"
  ln -sf "${shared_root}/doing" backlog/doing
  touch .gitignore
  if ! grep -qxF "backlog/doing" .gitignore; then
    printf '\n# maildir-shared backend — in-flight dir lives in git-common-dir\nbacklog/doing\n' >> .gitignore
  fi
  cat > backlog/AGENTS.md <<'EOF'
# backlog/

`CLAUDE.md` here is a symlink to this file — read one, not both.

Deferred work, one markdown file per task. Location = status:

- `todo/`  — available
- `doing/` — claimed, in flight (symlink into git-common-dir shared dir)
- `done/`  — completed (and cancelled — discriminated by the `cancelled` log line)

Use the `backlog` skill (add / advance / progress / cancel / fail / rescue / retry / maintain / status) to interact. Schema: the `backlog` skill's `references/agents-schema.md`.

## Backend

`maildir-shared` — `todo/`, `done/`, `failed/` are committed to git; `doing/` is a gitignored symlink into `$(git rev-parse --git-common-dir)/backlog/doing`. Claim is atomic across worktrees. See the `backlog` skill's `references/backends/maildir-shared.md`.

## Defaults

- `priority: 999` (declare to drive auto-pick ordering)
- `timeout: 7d`
- `dependencies: {}`

## Pipeline

`todo → doing → done`

## ROADMAP

Strategic counterpart at `backlog/ROADMAP.md`. See the `backlog` skill's `references/roadmap.md`.
EOF
  ln -sf AGENTS.md backlog/CLAUDE.md
  [[ -f backlog/ROADMAP.md ]] || cat > backlog/ROADMAP.md <<'EOF'
# ROADMAP

## Intent
<!-- One paragraph. -->

## Principles
<!-- 3–7 short statements. -->

## Current Focus
<!-- 1–3 paragraphs. -->

## Priorities
<!-- Ordered named arcs. -->

## Non-goals
<!-- What we are explicitly not doing right now. -->
EOF
  git add .gitignore backlog/AGENTS.md backlog/CLAUDE.md backlog/ROADMAP.md
  git commit -m "setup backlog (maildir-shared)"
}

cmd_add() {
  local slug="${1:?slug required}"
  local category="${2:-plan}"
  local first_dir
  first_dir="$(backlog_first_dir)"
  [[ -z "$first_dir" ]] && first_dir="todo"
  local file="backlog/${first_dir}/${slug}-${category}.md"
  [[ -f "$file" ]] && { echo "$file exists" >&2; exit 1; }
  mkdir -p "backlog/${first_dir}"
  cat > "$file" <<EOF
# ${slug}

[problem, decisions, phases, acceptance]

---
EOF
  git add "$file"
  git commit -m "add(${slug}-${category})"
  echo "$file"
}

cmd_advance() {
  ensure_symlinks
  local slug="${1:?slug required}"
  local src curr
  if [[ -f "backlog/todo/${slug}.md" ]]; then
    src="backlog/todo/${slug}.md"; curr="todo"
  elif src=$(find_shared "$slug"); then
    curr="$(basename "$(dirname "$src")")"
  else
    echo "no such task: $slug" >&2; exit 1
  fi

  local next; next=$(backlog_next_dir "$curr")
  [[ -z "$next" ]] && { echo "no next dir from $curr" >&2; exit 1; }

  local dst
  if [[ "$next" == "done" || "$next" == "failed" ]]; then
    mkdir -p "backlog/${next}"
    dst="backlog/${next}/${slug}.md"
  else
    mkdir -p "${shared_root}/${next}"
    dst="${shared_root}/${next}/${slug}.md"
  fi

  local ts; ts=$(backlog_now)

  if [[ "$curr" == "todo" ]]; then
    # Entry: cross-worktree atomic claim via O_EXCL
    if ! ( set -o noclobber; cat "$src" > "$dst" ) 2>/dev/null; then
      echo "claim conflict: $slug already in flight (another worktree)" >&2
      exit 1
    fi
    # If git rm fails, roll back the shared-file create so the slug stays takeable.
    if ! git rm "$src" >/dev/null 2>&1; then
      rm -f "$dst"
      echo "claim rollback: git rm failed for $src" >&2
      exit 1
    fi
    backlog_ensure_divider "$dst"
    local claimer branch
    claimer=$(backlog_claimer); branch=$(backlog_branch)
    echo "- $ts advanced to=$next claimer=$claimer branch=$branch" >> "$dst"
    git commit -m "advance($slug) → $next ($claimer @ $branch)" >/dev/null
  elif [[ "$next" == "done" || "$next" == "failed" ]]; then
    # Exit: shared -> worktree, commit
    mv "$src" "$dst"
    backlog_ensure_divider "$dst"
    local pr_url=""
    [[ "$next" == "done" ]] && pr_url=$(gh pr view --json url -q .url 2>/dev/null || true)
    local line="- $ts advanced to=$next"
    [[ -n "$pr_url" ]] && line+=" | PR=$pr_url"
    echo "$line" >> "$dst"
    git add "$dst"
    git commit -m "advance($slug) → $next${pr_url:+ PR=$pr_url}" >/dev/null
  else
    # Intermediate hop within shared — no commit (file isn't in tree)
    mv "$src" "$dst"
    backlog_ensure_divider "$dst"
    echo "- $ts advanced to=$next" >> "$dst"
  fi
  echo "$dst"
}

cmd_take() {
  ensure_symlinks
  local slug="${1:-}"
  if [[ -z "$slug" ]]; then
    # Auto-pick: lower priority first, recency tiebreaker, skip unresolved deps,
    # exclude slugs already in flight in any sibling worktree. Arc-aware
    # ranking lives in the worker loop (which reads ROADMAP.md).
    local in_flight
    in_flight=$(find "$shared_root" -mindepth 2 -maxdepth 2 -name '*.md' -type f -exec basename {} .md \; 2>/dev/null | sort -u)
    local best="" best_prio="" best_mtime=""
    local f s p mt
    for f in $(ls -t backlog/todo/*.md 2>/dev/null || true); do
      s=$(basename "$f" .md)
      grep -qx "$s" <<<"$in_flight" && continue       # already claimed elsewhere
      backlog_deps_resolved "$f" || continue
      p=$(backlog_priority "$f")
      mt=$(stat -f '%m' "$f" 2>/dev/null || stat -c '%Y' "$f" 2>/dev/null)
      if [[ -z "$best" ]] \
         || (( p < best_prio )) \
         || ( (( p == best_prio )) && (( mt > best_mtime )) ); then
        best="$f"; best_prio="$p"; best_mtime="$mt"
      fi
    done
    [[ -z "$best" ]] && { echo "no available tasks" >&2; exit 0; }
    slug=$(basename "$best" .md)
  fi
  cmd_advance "$slug"
}

cmd_progress() {
  ensure_symlinks
  local note="${1:?note required}"
  local branch; branch=$(backlog_branch)
  local file=""
  local d f last
  for d in "${shared_root}"/*/; do
    for f in "$d"*.md; do
      [[ -f "$f" ]] || continue
      last=$(grep -oE 'branch=[^ ]+' "$f" | tail -1 | cut -d= -f2)
      if [[ "$last" == "$branch" ]]; then
        file="$f"; break 2
      fi
    done
  done
  [[ -z "$file" ]] && { echo "no in-flight task claimed by branch $branch" >&2; exit 1; }
  local ts; ts=$(backlog_now)
  echo "- $ts progress | $note" >> "$file"
  # No commit — file isn't in tree
  echo "$file"
}

cmd_cancel() {
  ensure_symlinks
  local slug="${1:?slug required}"
  local reason="${2:?reason required}"
  local src; src=$(find_shared "$slug") || { echo "$slug not in-flight" >&2; exit 1; }
  local dst="backlog/done/${slug}.md"
  mkdir -p backlog/done
  mv "$src" "$dst"
  local ts; ts=$(backlog_now)
  echo "- $ts cancelled | $reason" >> "$dst"
  git add "$dst"
  git commit -m "cancel($slug) $reason" >/dev/null
}

cmd_fail() {
  ensure_symlinks
  local slug="${1:?slug required}"
  local reason="${2:?reason required}"
  local src; src=$(find_shared "$slug") || { echo "$slug not in-flight" >&2; exit 1; }
  mkdir -p backlog/failed
  local dst="backlog/failed/${slug}.md"
  mv "$src" "$dst"
  local ts; ts=$(backlog_now)
  echo "- $ts failed | $reason" >> "$dst"
  git add "$dst"
  git commit -m "fail($slug) $reason" >/dev/null
}

cmd_rescue() {
  ensure_symlinks
  local slug="${1:?slug required}"
  local file; file=$(find_shared "$slug") || { echo "$slug not in-flight" >&2; exit 1; }
  local secs; secs=$(backlog_timeout_seconds "$file")
  local last; last=$(grep -E '^- [0-9TZ:-]+ (advanced|rescued) ' "$file" | tail -1 | awk '{print $2}')
  [[ -z "$last" ]] && { echo "no prior claim line" >&2; exit 1; }
  local ep; ep=$(backlog_epoch "$last")
  [[ -z "$ep" ]] && { echo "unparseable timestamp: $last" >&2; exit 1; }
  (( $(date -u +%s) - ep > secs )) || { echo "claim still active; refusing rescue" >&2; exit 1; }
  local ts claimer branch
  ts=$(backlog_now); claimer=$(backlog_claimer); branch=$(backlog_branch)
  echo "- $ts rescued claimer=$claimer branch=$branch" >> "$file"
  # No commit — file isn't in tree
}

cmd_retry() {
  local slug="${1:?slug required}"
  local reason="${2:?reason required}"
  local src="backlog/failed/${slug}.md"
  [[ -f "$src" ]] || { echo "not in failed/: $slug" >&2; exit 1; }
  git mv "$src" "backlog/todo/${slug}.md"
  local ts; ts=$(backlog_now)
  echo "- $ts retried | $reason" >> "backlog/todo/${slug}.md"
  git add "backlog/todo/${slug}.md"
  git commit -m "retry($slug) $reason" >/dev/null
}

cmd_status() {
  ensure_symlinks
  local pile
  for pile in todo done failed; do
    printf "%s: %d\n" "$pile" "$(find "backlog/$pile" -name '*.md' -type f 2>/dev/null | wc -l | tr -d ' ')"
  done
  local d
  for d in "${shared_root}"/*/; do
    [[ -d "$d" ]] || continue
    printf "%s: %d\n" "$(basename "${d%/}")" "$(find "$d" -name '*.md' -type f | wc -l | tr -d ' ')"
  done
}

cmd_maintain() {
  echo "maintain: load ~/.claude/skills/backlog/references/maintain.md and walk the buckets" >&2
  echo "(this script doesn't enumerate them — they're advisory and benefit from agent judgment)"
}

cmd="${1:-}"
shift || true
case "$cmd" in
  setup)    cmd_setup "$@" ;;
  add)      cmd_add "$@" ;;
  take)     cmd_take "$@" ;;
  advance)  cmd_advance "$@" ;;
  progress) cmd_progress "$@" ;;
  cancel)   cmd_cancel "$@" ;;
  fail)     cmd_fail "$@" ;;
  rescue)   cmd_rescue "$@" ;;
  retry)    cmd_retry "$@" ;;
  status)   cmd_status "$@" ;;
  maintain)    cmd_maintain "$@" ;;
  *)        echo "unknown subcommand: $cmd" >&2; exit 1 ;;
esac
