#!/usr/bin/env bash
#MISE description="Create generated ~/.agents runtime from public sources and pinned third parties"
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.config/dotfiles}"
REPO_AGENTS="$DOTFILES_DIR/agents/shared"
HOME_AGENTS="${DOTFILES_AGENTS_HOME:-$HOME/.agents}"
MIGRATION_ROOT="${DOTFILES_MIGRATION_BACKUP_ROOT:-$HOME/.local/share/dotfiles/migration-backups}"

if [[ ! -d "$REPO_AGENTS" ]]; then
	echo "FAIL: $REPO_AGENTS missing — repo is incomplete" >&2
	exit 1
fi

realpath_py() {
	python3 - "$1" <<'PY'
import os, sys
print(os.path.realpath(os.path.expanduser(sys.argv[1])))
PY
}

backup_path() {
	local path="$1" label="$2" backup
	mkdir -p "$MIGRATION_ROOT"
	backup="$MIGRATION_ROOT/${label}-$(date -u +%Y%m%dT%H%M%SZ)-$$"
	mv "$path" "$backup"
	printf 'BACKED UP: %s -> %s\n' "$path" "$backup" >&2
}

ensure_source_link() {
	local name="$1" source="$REPO_AGENTS/$1" destination="$HOME_AGENTS/$1"
	[[ -e "$source" ]] || return 0
	if [[ -L "$destination" ]] \
		&& [[ "$(realpath_py "$destination")" == "$(realpath_py "$source")" ]]; then
		echo "OK: $destination -> $source"
		return
	fi
	if [[ -e "$destination" || -L "$destination" ]]; then
		backup_path "$destination" "agents-$name"
	fi
	ln -s "$source" "$destination"
	echo "LINKED: $destination -> $source"
}

# A legacy installation made ~/.agents a symlink to the public checkout. The
# symlink itself has no private content, so replace only the link; its target is
# preserved and any ignored runtime below it is migrated separately.
if [[ -L "$HOME_AGENTS" ]]; then
	if [[ "$(realpath_py "$HOME_AGENTS")" == "$(realpath_py "$REPO_AGENTS")" ]]; then
		rm "$HOME_AGENTS"
		echo "MIGRATED: removed legacy ~/.agents -> public checkout symlink"
	else
		backup_path "$HOME_AGENTS" "agents-home-symlink"
	fi
elif [[ -e "$HOME_AGENTS" && ! -d "$HOME_AGENTS" ]]; then
	backup_path "$HOME_AGENTS" "agents-home-path"
fi
mkdir -p "$HOME_AGENTS"

# Preserve runtime created by the previous topology before anything writes to
# the new generated store. These paths are ignored by Git but still do not
# belong inside the public checkout.
for legacy_name in skills runtime-backups; do
	legacy_path="$REPO_AGENTS/$legacy_name"
	if [[ -e "$legacy_path" || -L "$legacy_path" ]]; then
		backup_path "$legacy_path" "repo-agents-$legacy_name"
	fi
done

# Public read-only assets may be linked into the generated runtime. Mutable
# skills are handled separately below.
ensure_source_link prompts
ensure_source_link scripts

if [[ "${DOTFILES_SKIP_THIRD_PARTY_SKILLS:-0}" == "1" ]]; then
	"$DOTFILES_DIR/scripts/restore-shared-skills.sh" --first-party-only
else
	"$DOTFILES_DIR/scripts/restore-shared-skills.sh"
fi

# Pi consumes the generated shared skill store through a whole-directory link.
PI_SKILLS="$HOME/.pi/agent/skills"
EXPECTED_PI_SKILLS="$HOME_AGENTS/skills"
mkdir -p "$(dirname "$PI_SKILLS")"
if [[ -L "$PI_SKILLS" ]]; then
	current_target="$(readlink "$PI_SKILLS")"
	if [[ "$current_target" == "$EXPECTED_PI_SKILLS" ]]; then
		echo "OK: ~/.pi/agent/skills -> ~/.agents/skills"
	else
		ln -sfn "$EXPECTED_PI_SKILLS" "$PI_SKILLS"
		echo "RELINKED: ~/.pi/agent/skills -> ~/.agents/skills"
	fi
elif [[ -e "$PI_SKILLS" ]]; then
	echo "WARN: ~/.pi/agent/skills exists as a real path; leaving untouched" >&2
else
	ln -s "$EXPECTED_PI_SKILLS" "$PI_SKILLS"
	echo "LINKED: ~/.pi/agent/skills -> ~/.agents/skills"
fi

if [[ -x "$HOME_AGENTS/scripts/check-shared-skills.sh" ]]; then
	AGENTS_HOME="$HOME_AGENTS" "$HOME_AGENTS/scripts/check-shared-skills.sh" >/dev/null
	echo "OK: shared skills audit completed"
else
	echo "WARN: shared skills audit script missing or not executable" >&2
fi
