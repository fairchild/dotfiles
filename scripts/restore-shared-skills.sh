#!/usr/bin/env bash
#MISE description="Link dotclaude-authored skills and restore pinned third-party skills"
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.config/dotfiles}"
SOURCE_ROOT="$DOTFILES_DIR/agents/shared"
# Skills I author live in dotclaude; this repo links them rather than keeping copies.
DOTCLAUDE_SKILLS="${DOTFILES_DOTCLAUDE_SKILLS:-$HOME/.claude/skills}"
LEGACY_FIRST_PARTY_DIR="$SOURCE_ROOT/first-party-skills"
AGENTS_HOME="${DOTFILES_AGENTS_HOME:-${AGENTS_HOME:-$HOME/.agents}}"
RUNTIME_DIR="$AGENTS_HOME/skills"
LOCK_FILE="$SOURCE_ROOT/third-party-skills.lock.json"
BACKUP_ROOT="${DOTFILES_MIGRATION_BACKUP_ROOT:-$HOME/.local/share/dotfiles/migration-backups}/skills"
MODE="${1:-all}"

case "$MODE" in
	all|--first-party-only|--check|--check-first-party) ;;
	*) echo "usage: $0 [--first-party-only|--check|--check-first-party]" >&2; exit 2 ;;
esac

for command_name in git jq patch; do
	command -v "$command_name" >/dev/null 2>&1 \
		|| { echo "FAIL: required command not found: $command_name" >&2; exit 1; }
done

if [[ ! -f "$LOCK_FILE" ]]; then
	echo "FAIL: shared skill sources or lockfile missing under $SOURCE_ROOT" >&2
	exit 1
fi

mkdir -p "$RUNTIME_DIR"

realpath_py() {
	python3 - "$1" <<'PY'
import os, sys
print(os.path.realpath(os.path.expanduser(sys.argv[1])))
PY
}

backup_destination() {
	local destination="$1" name="$2" backup
	mkdir -p "$BACKUP_ROOT"
	backup="$BACKUP_ROOT/${name}-$(date -u +%Y%m%dT%H%M%SZ)-$$"
	mv "$destination" "$backup"
	echo "BACKED UP: unmanaged $destination -> $backup"
}

lock_install_names() {
	jq -r '.skills | to_entries[] | (.value.installName // .key)' "$LOCK_FILE"
}

# Every real skill directory in dotclaude, tracked or local tier. Symlinks there
# already point into this runtime, and names the lock claims stay third-party.
dotclaude_skill_dirs() {
	local dir name
	[[ -d "$DOTCLAUDE_SKILLS" ]] || return 0
	for dir in "$DOTCLAUDE_SKILLS"/*/; do
		dir="${dir%/}"
		name="${dir##*/}"
		[[ -L "$dir" || ! -f "$dir/SKILL.md" ]] && continue
		grep -Fxq "$name" <<< "$LOCK_NAMES" && continue
		printf '%s\n' "$dir"
	done
}

# A link this installer made: into dotclaude, or into the retired in-repo store.
managed_link() {
	local target
	target="$(readlink "$1")"
	[[ "$target" == "$DOTCLAUDE_SKILLS"/* || "$target" == "$LEGACY_FIRST_PARTY_DIR"/* ]]
}

materialize_first_party() {
	local source name destination link stale=0
	if [[ ! -d "$DOTCLAUDE_SKILLS" ]]; then
		echo "SKIP: no dotclaude skills at $DOTCLAUDE_SKILLS"
	fi
	while IFS= read -r source; do
		[[ -n "$source" ]] || continue
		name="${source##*/}"
		destination="$RUNTIME_DIR/$name"
		if [[ -L "$destination" && "$(readlink "$destination")" == "$source" ]]; then
			continue
		fi
		if [[ "$MODE" == "--check" || "$MODE" == "--check-first-party" ]]; then
			echo "FAIL: dotclaude skill is not linked into runtime: $name" >&2
			return 1
		fi
		if [[ -e "$destination" || -L "$destination" ]]; then
			if [[ -L "$destination" ]] && managed_link "$destination"; then
				rm "$destination"
			else
				backup_destination "$destination" "$name"
			fi
		fi
		ln -s "$source" "$destination"
	done < <(dotclaude_skill_dirs)

	# Retire links whose source is gone: the old in-repo store, or a removed dotclaude skill.
	for link in "$RUNTIME_DIR"/*; do
		[[ -L "$link" && ! -e "$link" ]] && managed_link "$link" || continue
		if [[ "$MODE" == "--check" || "$MODE" == "--check-first-party" ]]; then
			echo "FAIL: stale skill link: ${link##*/} -> $(readlink "$link")" >&2
			stale=1
		else
			rm "$link"
			echo "PRUNED: stale skill link ${link##*/}"
		fi
	done
	return "$stale"
}

check_third_party() {
	local missing=0 name install_name ref tree marker
	while IFS=$'\t' read -r name install_name ref tree; do
		marker="$RUNTIME_DIR/$install_name/.dotfiles-managed.json"
		if [[ ! -f "$RUNTIME_DIR/$install_name/SKILL.md" || ! -f "$marker" ]]; then
			echo "FAIL: third-party skill is not managed: $install_name ($name)" >&2
			missing=1
			continue
		fi
		jq -e --arg name "$name" --arg ref "$ref" --arg tree "$tree" \
			'.name == $name and .ref == $ref and .gitTree == $tree' "$marker" >/dev/null \
			|| { echo "FAIL: third-party marker drift: $install_name" >&2; missing=1; }
	done < <(jq -r '.skills | to_entries[] | [.key, (.value.installName // .key), .value.ref, .value.gitTree] | @tsv' "$LOCK_FILE")
	return "$missing"
}

prepare_third_party_destination() {
	local destination="$1" name="$2" marker="$1/.dotfiles-managed.json"
	if [[ ! -e "$destination" && ! -L "$destination" ]]; then
		return
	fi
	if [[ -f "$marker" ]] && jq -e --arg name "$name" '.name == $name' "$marker" >/dev/null 2>&1; then
		rm -rf "$destination"
	else
		backup_destination "$destination" "$name"
	fi
}

restore_third_party() {
	local temp_root checkout current_key="" index=0
	local name install_name source_url ref skill_path expected_tree patch_file skill_dir actual_tree destination
	temp_root="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-skills.XXXXXX")"
	trap '[[ -z "${temp_root:-}" ]] || rm -rf "$temp_root"' EXIT

	while IFS=$'\t' read -r name install_name source_url ref skill_path expected_tree patch_file; do
		if [[ "$source_url@$ref" != "$current_key" ]]; then
			current_key="$source_url@$ref"
			index=$((index + 1))
			checkout="$temp_root/source-$index"
			git init -q "$checkout"
			git -C "$checkout" remote add origin "$source_url"
			git -C "$checkout" fetch -q --depth=1 origin "$ref"
			git -C "$checkout" checkout -q --detach FETCH_HEAD
		fi

		skill_dir="${skill_path%/SKILL.md}"
		actual_tree="$(git -C "$checkout" rev-parse "HEAD:$skill_dir")"
		if [[ "$actual_tree" != "$expected_tree" ]]; then
			echo "FAIL: upstream tree mismatch for $name" >&2
			printf '\texpected: %s\n' "$expected_tree" >&2
			printf '\tactual:   %s\n' "$actual_tree" >&2
			exit 1
		fi

		destination="$RUNTIME_DIR/$install_name"
		prepare_third_party_destination "$destination" "$name"
		mkdir -p "$destination"
		cp -R "$checkout/$skill_dir/." "$destination/"
		if [[ -n "$patch_file" ]]; then
			patch -s -d "$destination" -p1 < "$SOURCE_ROOT/$patch_file"
		fi
		jq -n --arg name "$name" --arg sourceUrl "$source_url" --arg ref "$ref" --arg gitTree "$expected_tree" \
			'{name: $name, sourceUrl: $sourceUrl, ref: $ref, gitTree: $gitTree}' \
			> "$destination/.dotfiles-managed.json"
		echo "RESTORED: $install_name from ${source_url#https://github.com/}@$ref"
	done < <(
		jq -r '.skills | to_entries | sort_by(.value.sourceUrl, .value.ref, .key)[] |
			[.key, (.value.installName // .key), .value.sourceUrl, .value.ref,
			 .value.skillPath, .value.gitTree, (.value.patch // "")] | @tsv' "$LOCK_FILE"
	)
}

LOCK_NAMES="$(lock_install_names)"
materialize_first_party

case "$MODE" in
	--check)
		check_third_party
		echo "OK: generated skill runtime matches public sources and lock inventory"
		;;
	--check-first-party)
		echo "OK: generated runtime links every dotclaude skill"
		;;
	--first-party-only)
		echo "OK: dotclaude skills linked into generated runtime"
		;;
	all)
		restore_third_party
		check_third_party
		echo "OK: dotclaude skills linked and pinned third-party skills materialized outside the checkout"
		;;
esac
