#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../scripts/lib.sh
. "$script_dir/../scripts/lib.sh"

repo_root="$PWD"
if detected_root=$(git rev-parse --show-toplevel 2>/dev/null); then
  repo_root="$detected_root"
  cd "$repo_root"
fi

normalize_path() {
  local file="$1"

  if [[ "$file" = /* ]]; then
    case "$file" in
      "$repo_root"/*) file="${file#"$repo_root"/}" ;;
    esac
  fi

  printf '%s\n' "$file"
}

is_backlog_markdown() {
  local file="$1"
  [[ "$file" == backlog/*.md && "$file" == *.md ]]
}

dep_resolves() {
  local dep="$1"
  local found=""

  if [[ -d backlog ]]; then
    found=$(find -L backlog -mindepth 2 -maxdepth 2 -type f -name "${dep}.md" -print -quit 2>/dev/null || true)
    [[ -n "$found" ]] && return 0
  fi

  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    found=$(git ls-files --cached -- "backlog/*/${dep}.md" 2>/dev/null || true)
    [[ -n "$found" ]] && return 0
  fi

  return 1
}

failed=0

for arg in "$@"; do
  file=$(normalize_path "$arg")
  is_backlog_markdown "$file" || continue
  [[ -f "$file" ]] || continue

  while IFS= read -r dep; do
    [[ -n "$dep" ]] || continue

    if ! dep_resolves "$dep"; then
      printf 'backlog: unresolved dep in %s: %s\n' "$file" "$dep" >&2
      printf '  -> author it with: bash ~/.claude/skills/backlog/scripts/backlog.sh add %s [followup|plan|task-list|ideas]\n' "$dep" >&2
      failed=1
    fi
  done < <(backlog_deps "$file")
done

exit "$failed"
