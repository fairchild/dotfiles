#!/usr/bin/env bash
set -euo pipefail

AGENTS_HOME="${AGENTS_HOME:-$HOME/.agents}"
CANONICAL_SKILLS_DIR="$AGENTS_HOME/skills"
APPLY=0
FORCE=0
ALL=0
TARGET=""
SKILLS=()

usage() {
  cat <<'EOF'
Usage:
  link-shared-skills.sh [--dry-run|--apply] [--force] <claude|codex|pi> <skill> [skill...]
  link-shared-skills.sh [--dry-run|--apply] [--force] --all <claude|codex>
  link-shared-skills.sh [--dry-run|--apply] pi

Examples:
  link-shared-skills.sh claude code-review voice
  link-shared-skills.sh --apply claude code-review voice
  link-shared-skills.sh --apply --all codex
  link-shared-skills.sh pi

Notes:
  - Default mode is --dry-run.
  - pi is managed as a whole-directory symlink: ~/.pi/agent/skills -> ~/.agents/skills.
  - claude and codex are managed as per-skill symlinks into ~/.agents/skills.
  - Existing real directories are never replaced unless you manually move/remove them first.
EOF
}

realpath_py() {
  python3 - "$1" <<'PY'
import os, sys
print(os.path.realpath(sys.argv[1]))
PY
}

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

log() {
  printf '%s\n' "$*"
}

warn() {
  printf 'WARN: %s\n' "$*" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      APPLY=0
      shift
      ;;
    --apply)
      APPLY=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --all)
      ALL=1
      shift
      ;;
    claude|codex|pi)
      TARGET="$1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      SKILLS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  usage
  exit 1
fi

if [[ ! -d "$CANONICAL_SKILLS_DIR" ]]; then
  warn "Canonical skills dir not found: $CANONICAL_SKILLS_DIR"
  exit 1
fi
CANONICAL_SKILLS_REALPATH="$(realpath_py "$CANONICAL_SKILLS_DIR")"

case "$TARGET" in
  claude)
    DEST_DIR="$HOME/.claude/skills"
    ;;
  codex)
    DEST_DIR="$HOME/.Codex/skills"
    ;;
  pi)
    DEST_DIR="$HOME/.pi/agent/skills"
    ;;
esac

mkdir -p "$(dirname "$DEST_DIR")"

if [[ "$TARGET" == "pi" ]]; then
  current_realpath=""
  if [[ -e "$DEST_DIR" ]]; then
    current_realpath="$(realpath_py "$DEST_DIR")"
  fi

  if [[ "$current_realpath" == "$CANONICAL_SKILLS_REALPATH" ]]; then
    log "OK: $DEST_DIR already points at $CANONICAL_SKILLS_DIR"
    exit 0
  fi

  if [[ -e "$DEST_DIR" && ! -L "$DEST_DIR" ]]; then
    warn "$DEST_DIR exists as a real directory. Refusing to replace it automatically."
    warn "Move it aside manually, then rerun with --apply."
    exit 1
  fi

  if [[ "$APPLY" -eq 1 ]]; then
    rm -f "$DEST_DIR"
    ln -s "$CANONICAL_SKILLS_DIR" "$DEST_DIR"
    log "LINKED: $DEST_DIR -> $CANONICAL_SKILLS_DIR"
  else
    log "DRY-RUN: would link $DEST_DIR -> $CANONICAL_SKILLS_DIR"
  fi
  exit 0
fi

mkdir -p "$DEST_DIR"

if [[ "$ALL" -eq 1 ]]; then
  while IFS= read -r skill; do
    SKILLS+=("$skill")
  done < <(find "$CANONICAL_SKILLS_DIR" -maxdepth 1 -mindepth 1 \( -type d -o -type l \) -exec basename {} \; | sort)
fi

if [[ ${#SKILLS[@]} -eq 0 ]]; then
  warn "No skills provided."
  usage
  exit 1
fi

UNIQUE_SKILLS=()
for skill in "${SKILLS[@]}"; do
  [[ -n "$skill" ]] || continue
  duplicate=0
  for existing in "${UNIQUE_SKILLS[@]:-}"; do
    if [[ "$existing" == "$skill" ]]; then
      duplicate=1
      break
    fi
  done
  if [[ "$duplicate" -eq 0 ]]; then
    UNIQUE_SKILLS+=("$skill")
  fi
done

for skill in "${UNIQUE_SKILLS[@]}"; do
  src="$CANONICAL_SKILLS_DIR/$skill"
  dst="$DEST_DIR/$skill"

  if [[ ! -d "$src" ]]; then
    warn "Missing canonical skill: $src"
    continue
  fi

  skill_md="$src/SKILL.md"
  if [[ ! -f "$skill_md" ]]; then
    warn "Missing SKILL.md: $skill_md"
    continue
  fi

  declared_name="$(skill_frontmatter_name "$skill_md")"
  if [[ -z "$declared_name" ]]; then
    warn "Could not read skill name from $skill_md"
    continue
  fi

  if [[ "$declared_name" != "$skill" ]]; then
    warn "Name mismatch for $src (frontmatter=$declared_name dir=$skill). Skipping."
    continue
  fi

  if [[ -L "$dst" ]]; then
    dst_realpath="$(realpath_py "$dst")"
    src_realpath="$(realpath_py "$src")"
    if [[ "$dst_realpath" == "$src_realpath" ]]; then
      log "OK: $dst -> $src"
      continue
    fi

    if [[ "$FORCE" -eq 1 ]]; then
      if [[ "$APPLY" -eq 1 ]]; then
        rm -f "$dst"
        ln -s "$src" "$dst"
        log "RELINKED: $dst -> $src"
      else
        log "DRY-RUN: would relink $dst -> $src"
      fi
    else
      warn "$dst points elsewhere ($dst_realpath). Use --force to relink."
    fi
    continue
  fi

  if [[ -e "$dst" ]]; then
    warn "$dst exists as a real file/directory. Move it aside before linking."
    continue
  fi

  if [[ "$APPLY" -eq 1 ]]; then
    ln -s "$src" "$dst"
    log "LINKED: $dst -> $src"
  else
    log "DRY-RUN: would link $dst -> $src"
  fi
done
