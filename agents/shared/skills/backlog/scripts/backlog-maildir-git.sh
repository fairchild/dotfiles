#!/usr/bin/env bash
# maildir-git backend — everything in backlog/ is git-tracked; claim is `git mv`.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
. "$script_dir/lib.sh"

find_in_tree() {
  local slug="$1"
  find backlog -mindepth 2 -maxdepth 2 -name "${slug}.md" -type f 2>/dev/null | head -1
}

find_inflight() {
  local slug="$1"
  find backlog -mindepth 2 -maxdepth 2 -name "${slug}.md" -type f \
    ! -path 'backlog/todo/*' ! -path 'backlog/done/*' ! -path 'backlog/failed/*' 2>/dev/null | head -1
}

cmd_setup() {
  [[ -f backlog/AGENTS.md ]] && { echo "backlog/AGENTS.md exists — refusing to overwrite" >&2; exit 1; }
  mkdir -p backlog/{todo,doing,done}
  cat > backlog/AGENTS.md <<'EOF'
# backlog/

`CLAUDE.md` here is a symlink to this file — read one, not both.

Deferred work, one markdown file per task. Location = status:

- `todo/`  — available
- `doing/` — claimed, in flight
- `done/`  — completed (and cancelled — discriminated by the `cancelled` log line)

Use the `backlog` skill (add / advance / progress / cancel / fail / rescue / retry / maintain / status) to interact. Schema: the `backlog` skill's `references/agents-schema.md`.

## Backend

`maildir-git` — everything in this directory is committed to git; claim is `git mv`. See the `backlog` skill's `references/backends/maildir-git.md`.

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
<!-- One paragraph. What this project ultimately intends to be. -->

## Principles
<!-- 3–7 short statements. -->

## Current Focus
<!-- 1–3 paragraphs. The active arc. -->

## Priorities
<!-- Ordered named arcs (kebab-case). -->

## Non-goals
<!-- What we are explicitly not doing right now. -->
EOF
  git add backlog/AGENTS.md backlog/CLAUDE.md backlog/ROADMAP.md
  git commit -m "setup backlog (maildir-git)"
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
  local slug="${1:?slug required}"
  local src; src=$(find_in_tree "$slug") || true
  [[ -z "$src" ]] && { echo "no such task: $slug" >&2; exit 1; }
  local curr; curr=$(basename "$(dirname "$src")")
  local next; next=$(backlog_next_dir "$curr")
  [[ -z "$next" ]] && { echo "no next dir from $curr" >&2; exit 1; }

  local dst="backlog/${next}/${slug}.md"
  mkdir -p "backlog/${next}"
  git mv "$src" "$dst"
  backlog_ensure_divider "$dst"
  local ts; ts=$(backlog_now)

  if [[ "$curr" == "todo" ]]; then
    local claimer branch
    claimer=$(backlog_claimer); branch=$(backlog_branch)
    echo "- $ts advanced to=$next claimer=$claimer branch=$branch" >> "$dst"
    git add "$dst"
    git commit -m "advance($slug) → $next ($claimer @ $branch)"
  else
    local pr_url=""
    [[ "$next" == "done" ]] && pr_url=$(gh pr view --json url -q .url 2>/dev/null || true)
    local line="- $ts advanced to=$next"
    [[ -n "$pr_url" ]] && line+=" | PR=$pr_url"
    echo "$line" >> "$dst"
    git add "$dst"
    git commit -m "advance($slug) → $next${pr_url:+ PR=$pr_url}"
  fi
  echo "$dst"
}

cmd_take() {
  local slug="${1:-}"
  if [[ -z "$slug" ]]; then
    # Auto-pick: lower priority first, recency tiebreaker (newer wins),
    # skipping tasks with unresolved deps. Arc-aware ranking is left to
    # the worker loop (which reads ROADMAP.md).
    local best="" best_prio="" best_mtime=""
    local f p mt
    for f in $(ls -t backlog/todo/*.md 2>/dev/null || true); do
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
  local note="${1:?note required}"
  local branch; branch=$(backlog_branch)
  local file=""
  for f in $(find backlog -mindepth 2 -maxdepth 2 -type f -name '*.md' \
             ! -path 'backlog/todo/*' ! -path 'backlog/done/*' ! -path 'backlog/failed/*' 2>/dev/null); do
    local last; last=$(grep -oE 'branch=[^ ]+' "$f" | tail -1 | cut -d= -f2)
    [[ "$last" == "$branch" ]] && { file="$f"; break; }
  done
  [[ -z "$file" ]] && { echo "no in-flight task claimed by branch $branch" >&2; exit 1; }
  local ts; ts=$(backlog_now)
  echo "- $ts progress | $note" >> "$file"
  git add "$file"
  git commit -m "progress($(basename "$file" .md)) $note"
  echo "$file"
}

cmd_cancel() {
  local slug="${1:?slug required}"
  local reason="${2:?reason required}"
  local src; src=$(find_inflight "$slug") || true
  [[ -z "$src" ]] && { echo "$slug not in-flight" >&2; exit 1; }
  git mv "$src" "backlog/done/${slug}.md"
  local ts; ts=$(backlog_now)
  echo "- $ts cancelled | $reason" >> "backlog/done/${slug}.md"
  git add "backlog/done/${slug}.md"
  git commit -m "cancel($slug) $reason"
}

cmd_fail() {
  local slug="${1:?slug required}"
  local reason="${2:?reason required}"
  local src; src=$(find_inflight "$slug") || true
  [[ -z "$src" ]] && { echo "$slug not in-flight" >&2; exit 1; }
  mkdir -p backlog/failed
  git mv "$src" "backlog/failed/${slug}.md"
  local ts; ts=$(backlog_now)
  echo "- $ts failed | $reason" >> "backlog/failed/${slug}.md"
  git add "backlog/failed/${slug}.md"
  git commit -m "fail($slug) $reason"
}

cmd_rescue() {
  local slug="${1:?slug required}"
  local file; file=$(find_inflight "$slug") || true
  [[ -z "$file" ]] && { echo "$slug not in-flight" >&2; exit 1; }
  local secs; secs=$(backlog_timeout_seconds "$file")
  local last; last=$(grep -E '^- [0-9TZ:-]+ (advanced|rescued) ' "$file" | tail -1 | awk '{print $2}')
  [[ -z "$last" ]] && { echo "no prior claim line" >&2; exit 1; }
  local ep; ep=$(backlog_epoch "$last")
  [[ -z "$ep" ]] && { echo "unparseable timestamp: $last" >&2; exit 1; }
  (( $(date -u +%s) - ep > secs )) || { echo "claim still active; refusing rescue" >&2; exit 1; }
  local ts claimer branch
  ts=$(backlog_now); claimer=$(backlog_claimer); branch=$(backlog_branch)
  echo "- $ts rescued claimer=$claimer branch=$branch" >> "$file"
  git add "$file"
  git commit -m "rescue($slug) $claimer @ $branch"
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
  git commit -m "retry($slug) $reason"
}

cmd_status() {
  for pile in todo doing done failed; do
    printf "%s: %d\n" "$pile" "$(find "backlog/$pile" -name '*.md' -type f 2>/dev/null | wc -l | tr -d ' ')"
  done
  for d in $(find backlog -mindepth 1 -maxdepth 1 -type d ! -name todo ! -name doing ! -name done ! -name failed 2>/dev/null); do
    printf "%s: %d\n" "$(basename "$d")" "$(find "$d" -name '*.md' -type f | wc -l | tr -d ' ')"
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
