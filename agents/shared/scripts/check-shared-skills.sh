#!/usr/bin/env bash
set -euo pipefail

AGENTS_HOME="${AGENTS_HOME:-$HOME/.agents}"
CANONICAL_SKILLS_DIR="$AGENTS_HOME/skills"
PI_SKILLS_DIR="$HOME/.pi/agent/skills"
CLAUDE_SKILLS_DIR="$HOME/.claude/skills"
CODEX_SKILLS_DIR="$HOME/.Codex/skills"

realpath_py() {
  python3 - "$1" <<'PY'
import os, sys
print(os.path.realpath(sys.argv[1]))
PY
}

CANONICAL_SKILLS_REALPATH="$(realpath_py "$CANONICAL_SKILLS_DIR")"

skill_frontmatter_name() {
  local skill_md="$1"
  awk '
    BEGIN { inmeta=0 }
    /^---[[:space:]]*$/ {
      if (inmeta == 0) { inmeta=1; next }
      exit
    }
    inmeta == 1 && $1 == "name:" {
      value=$0
      sub(/^[^:]+:[[:space:]]*/, "", value)
      gsub(/^"|"$/, "", value)
      gsub(/^'"'"'|'"'"'$/, "", value)
      print value
      exit
    }
  ' "$skill_md"
}

count_links_to_canonical() {
  local dest_dir="$1"
  local count=0
  [[ -d "$dest_dir" ]] || { echo 0; return; }
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    if [[ -L "$path" ]]; then
      target="$(realpath_py "$path")"
      case "$target" in
        "$CANONICAL_SKILLS_REALPATH"/*) count=$((count + 1)) ;;
      esac
    fi
  done < <(find "$dest_dir" -maxdepth 1 -mindepth 1 \( -type d -o -type l \) -print)
  echo "$count"
}

find_non_symlink_duplicates() {
  local dest_dir="$1"
  [[ -d "$dest_dir" ]] || return
  while IFS= read -r skill; do
    dst="$dest_dir/$skill"
    if [[ -d "$dst" && ! -L "$dst" ]]; then
      echo "$skill"
    fi
  done < <(find "$CANONICAL_SKILLS_DIR" -maxdepth 1 -mindepth 1 \( -type d -o -type l \) -exec basename {} \; | sort)
}

printf '## Shared Skills Audit\n\n'
printf 'Canonical store: %s\n\n' "$CANONICAL_SKILLS_DIR"

printf '### Canonical name checks\n'
name_issues=0
while IFS= read -r skill_dir; do
  skill="$(basename "$skill_dir")"
  skill_md="$skill_dir/SKILL.md"
  if [[ ! -f "$skill_md" ]]; then
    printf -- '- MISSING SKILL.md: %s\n' "$skill_dir"
    name_issues=$((name_issues + 1))
    continue
  fi
  declared_name="$(skill_frontmatter_name "$skill_md")"
  if [[ -z "$declared_name" ]]; then
    printf -- '- UNREADABLE name: %s\n' "$skill_md"
    name_issues=$((name_issues + 1))
  elif [[ "$declared_name" != "$skill" ]]; then
    printf -- '- MISMATCH: dir=%s frontmatter=%s\n' "$skill" "$declared_name"
    name_issues=$((name_issues + 1))
  fi
done < <(find "$CANONICAL_SKILLS_DIR" -maxdepth 1 -mindepth 1 \( -type d -o -type l \) | sort)
if [[ "$name_issues" -eq 0 ]]; then
  printf -- '- OK: all canonical skill directories match frontmatter names\n'
fi
printf '\n'

printf '### Runtime topology\n'
if [[ -e "$PI_SKILLS_DIR" ]]; then
  pi_realpath="$(realpath_py "$PI_SKILLS_DIR")"
  if [[ "$pi_realpath" == "$CANONICAL_SKILLS_REALPATH" ]]; then
    printf -- '- pi: OK whole-dir symlink/mount -> %s\n' "$CANONICAL_SKILLS_DIR"
  else
    printf -- '- pi: DRIFT -> %s\n' "$pi_realpath"
  fi
else
  printf -- '- pi: missing %s\n' "$PI_SKILLS_DIR"
fi

for pair in "claude:$CLAUDE_SKILLS_DIR" "codex:$CODEX_SKILLS_DIR"; do
  name="${pair%%:*}"
  dir="${pair#*:}"
  if [[ -d "$dir" ]]; then
    total="$(find "$dir" -maxdepth 1 -mindepth 1 \( -type d -o -type l \) | wc -l | tr -d ' ')"
    linked="$(count_links_to_canonical "$dir")"
    printf -- '- %s: %s entries, %s symlinked into canonical store\n' "$name" "$total" "$linked"
  else
    printf -- '- %s: missing %s\n' "$name" "$dir"
  fi
done
printf '\n'

printf '### Local duplicates that shadow canonical skills\n'
shadowed=0
for pair in "claude:$CLAUDE_SKILLS_DIR" "codex:$CODEX_SKILLS_DIR"; do
  name="${pair%%:*}"
  dir="${pair#*:}"
  dupes="$(find_non_symlink_duplicates "$dir" || true)"
  if [[ -n "$dupes" ]]; then
    shadowed=1
    printf -- '- %s:\n' "$name"
    while IFS= read -r skill; do
      [[ -n "$skill" ]] || continue
      printf '  - %s\n' "$skill"
    done <<< "$dupes"
  fi
done
if [[ "$shadowed" -eq 0 ]]; then
  printf -- '- OK: no local duplicates found\n'
fi
printf '\n'

printf '### Hardcoded harness-path references inside canonical skills\n'
if command -v rg >/dev/null 2>&1; then
  if rg -n --hidden --glob '!**/.git/**' '~/(\.claude|\.Codex|\.pi/agent)/skills/' "$CANONICAL_SKILLS_DIR" >/tmp/shared-skill-path-audit.$$ 2>/dev/null; then
    head -n 80 /tmp/shared-skill-path-audit.$$
    total_lines="$(wc -l < /tmp/shared-skill-path-audit.$$ | tr -d ' ')"
    if [[ "$total_lines" -gt 80 ]]; then
      printf '... (%s matches total)\n' "$total_lines"
    fi
  else
    printf -- '- OK: no hardcoded harness skill paths found\n'
  fi
  rm -f /tmp/shared-skill-path-audit.$$
else
  printf -- '- ripgrep not installed; skipping path scan\n'
fi
