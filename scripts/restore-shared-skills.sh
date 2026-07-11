#!/usr/bin/env bash
#MISE description="Materialize first-party skills and restore pinned third-party skills"
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.config/dotfiles}"
AGENTS_ROOT="$DOTFILES_DIR/agents/shared"
FIRST_PARTY_DIR="$AGENTS_ROOT/first-party-skills"
RUNTIME_DIR="$AGENTS_ROOT/skills"
LOCK_FILE="$AGENTS_ROOT/third-party-skills.lock.json"
MODE="${1:-all}"

case "$MODE" in
	all|--first-party-only|--check) ;;
	*)
		echo "usage: $0 [--first-party-only|--check]" >&2
		exit 2
		;;
esac

for command_name in git jq patch; do
	if ! command -v "$command_name" >/dev/null 2>&1; then
		echo "FAIL: required command not found: $command_name" >&2
		exit 1
	fi
done

if [[ ! -d "$FIRST_PARTY_DIR" || ! -f "$LOCK_FILE" ]]; then
	echo "FAIL: shared skill sources or lockfile missing under $AGENTS_ROOT" >&2
	exit 1
fi

mkdir -p "$RUNTIME_DIR"

materialize_first_party() {
	local source name destination expected
	while IFS= read -r source; do
		name="$(basename "$source")"
		destination="$RUNTIME_DIR/$name"
		expected="../first-party-skills/$name"

		if [[ -L "$destination" ]]; then
			if [[ "$(readlink "$destination")" == "$expected" ]]; then
				continue
			fi
			if [[ "$MODE" == "--check" ]]; then
				echo "FAIL: $destination points to $(readlink "$destination"), expected $expected" >&2
				return 1
			fi
			ln -sfn "$expected" "$destination"
		elif [[ -e "$destination" ]]; then
			echo "FAIL: refusing to replace non-symlink first-party destination: $destination" >&2
			return 1
		elif [[ "$MODE" == "--check" ]]; then
			echo "FAIL: first-party skill is not materialized: $name" >&2
			return 1
		else
			ln -s "$expected" "$destination"
		fi
	done < <(find "$FIRST_PARTY_DIR" -mindepth 1 -maxdepth 1 -type d | sort)
}

check_third_party() {
	local missing=0 name install_name
	while IFS=$'\t' read -r name install_name; do
		if [[ ! -f "$RUNTIME_DIR/$install_name/SKILL.md" ]]; then
			echo "FAIL: third-party skill is not materialized: $install_name ($name)" >&2
			missing=1
		fi
	done < <(jq -r '.skills | to_entries[] | [.key, (.value.installName // .key)] | @tsv' "$LOCK_FILE")
	return "$missing"
}

restore_third_party() {
	local temp_root checkout current_key="" index=0
	local name install_name source_url ref skill_path expected_tree patch_file skill_dir actual_tree destination
	temp_root="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-skills.XXXXXX")"
	trap '[[ -z "${temp_root:-}" ]] || rm -rf "$temp_root"' EXIT

	while IFS=$'\t' read -r name install_name source_url ref skill_path expected_tree patch_file; do
		if [[ -d "$FIRST_PARTY_DIR/$install_name" ]]; then
			echo "FAIL: third-party lock collides with first-party skill: $install_name" >&2
			exit 1
		fi

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
			echo "	expected: $expected_tree" >&2
			echo "	actual:	  $actual_tree" >&2
			exit 1
		fi

		destination="$RUNTIME_DIR/$install_name"
		rm -rf "$destination"
		mkdir -p "$destination"
		cp -R "$checkout/$skill_dir/." "$destination/"
		if [[ -n "$patch_file" ]]; then
			patch -s -d "$destination" -p1 < "$AGENTS_ROOT/$patch_file"
		fi
		echo "RESTORED: $install_name from ${source_url#https://github.com/}@$ref"
	done < <(
		jq -r '.skills | to_entries | sort_by(.value.sourceUrl, .value.ref, .key)[] |
			[.key, (.value.installName // .key), .value.sourceUrl, .value.ref,
			 .value.skillPath, .value.gitTree, (.value.patch // "")] | @tsv' "$LOCK_FILE"
	)
}

materialize_first_party

if [[ "$MODE" == "--check" ]]; then
	check_third_party
	echo "OK: shared skill runtime matches tracked sources and lock inventory"
elif [[ "$MODE" == "--first-party-only" ]]; then
	echo "OK: first-party skills materialized"
else
	restore_third_party
	check_third_party
	echo "OK: first-party and pinned third-party skills materialized"
fi
