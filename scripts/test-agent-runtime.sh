#!/usr/bin/env bash
#MISE description="Exercise non-destructive agent runtime migration in an isolated HOME"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

setup_source() {
	local name="$1"
	SOURCE="$tmp/source-$name"
	mkdir -p \
		"$SOURCE/scripts" \
		"$SOURCE/agents/shared/first-party-skills/example" \
		"$SOURCE/agents/shared/prompts" \
		"$SOURCE/agents/shared/scripts" \
		"$SOURCE/agents/shared/third-party-patches"
	cp "$ROOT/scripts/install-agents.sh" "$SOURCE/scripts/"
	cp "$ROOT/scripts/restore-shared-skills.sh" "$SOURCE/scripts/"
	cp "$ROOT/scripts/doctor.sh" "$SOURCE/scripts/"
	chmod +x "$SOURCE/scripts/install-agents.sh" "$SOURCE/scripts/restore-shared-skills.sh" "$SOURCE/scripts/doctor.sh"
	printf '%s\n' '---' 'name: example' 'description: fixture' '---' > "$SOURCE/agents/shared/first-party-skills/example/SKILL.md"
	printf '# prompt\n' > "$SOURCE/agents/shared/prompts/example.md"
	printf '#!/bin/sh\nexit 0\n' > "$SOURCE/agents/shared/scripts/check-shared-skills.sh"
	chmod +x "$SOURCE/agents/shared/scripts/check-shared-skills.sh"
	printf '{"version":1,"skills":{}}\n' > "$SOURCE/agents/shared/third-party-skills.lock.json"
}

run_first_party_install() {
	local fixture_home="$1" source="$2"
	HOME="$fixture_home" \
	DOTFILES_DIR="$source" \
	DOTFILES_SKIP_THIRD_PARTY_SKILLS=1 \
		"$source/scripts/install-agents.sh" >/dev/null
}

# Legacy whole-directory symlink and checkout-local runtime migrate out of Git.
setup_source legacy
legacy_source="$SOURCE"
legacy_home="$tmp/home-legacy"
mkdir -p "$legacy_home" "$legacy_source/agents/shared/skills/legacy"
printf 'old runtime\n' > "$legacy_source/agents/shared/skills/legacy/state.txt"
ln -s "$legacy_source/agents/shared" "$legacy_home/.agents"
run_first_party_install "$legacy_home" "$legacy_source"
HOME="$legacy_home" DOTFILES_DIR="$legacy_source" "$legacy_source/scripts/restore-shared-skills.sh" --check >/dev/null

[[ -d "$legacy_home/.agents" && ! -L "$legacy_home/.agents" ]]
[[ -L "$legacy_home/.agents/skills/example" ]]
[[ "$(readlink "$legacy_home/.agents/skills/example")" == "$legacy_source/agents/shared/first-party-skills/example" ]]
[[ -L "$legacy_home/.agents/prompts" && -L "$legacy_home/.agents/scripts" ]]
[[ -L "$legacy_home/.pi/agent/skills" ]]
[[ ! -e "$legacy_source/agents/shared/skills" ]]
find "$legacy_home/.local/share/dotfiles/migration-backups" -name state.txt -print -quit | grep -q .
doctor_output="$(HOME="$legacy_home" DOTFILES_DIR="$legacy_source" "$legacy_source/scripts/doctor.sh" 2>&1 || true)"
grep -q 'real generated runtime directory' <<< "$doctor_output"
grep -q 'generated skill runtime is outside the public checkout' <<< "$doctor_output"
grep -q 'shared skill runtime matches first-party sources and third-party lock\|shared skill runtime matches' <<< "$doctor_output"

backup_count_before="$(find "$legacy_home/.local/share/dotfiles/migration-backups" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')"
run_first_party_install "$legacy_home" "$legacy_source"
backup_count_after="$(find "$legacy_home/.local/share/dotfiles/migration-backups" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')"
[[ "$backup_count_before" == "$backup_count_after" ]]
printf 'PASS: legacy runtime migration is outside Git and idempotent\n'

# Existing real runtime is preserved; only managed destinations are replaced.
setup_source collision
collision_source="$SOURCE"
collision_home="$tmp/home-collision"
mkdir -p "$collision_home/.agents/skills/example" "$collision_home/.agents/prompts"
printf 'private skill state\n' > "$collision_home/.agents/skills/example/local.txt"
printf 'private prompts\n' > "$collision_home/.agents/prompts/local.txt"
run_first_party_install "$collision_home" "$collision_source"

[[ -L "$collision_home/.agents/skills/example" ]]
[[ -L "$collision_home/.agents/prompts" ]]
find "$collision_home/.local/share/dotfiles/migration-backups" -name local.txt -exec grep -l 'private skill state' {} \; | grep -q .
find "$collision_home/.local/share/dotfiles/migration-backups" -name local.txt -exec grep -l 'private prompts' {} \; | grep -q .
printf 'PASS: unmanaged runtime collisions are backed up before linking\n'

# A pinned local upstream exercises third-party restore and managed markers.
setup_source third-party
third_source="$SOURCE"
third_home="$tmp/home-third"
upstream="$tmp/upstream"
mkdir -p "$upstream/skills/third" "$third_home"
git -C "$upstream" init -q
git -C "$upstream" config user.name fixture
git -C "$upstream" config user.email fixture@example.com
printf '%s\n' '---' 'name: third' 'description: fixture' '---' > "$upstream/skills/third/SKILL.md"
git -C "$upstream" add .
git -C "$upstream" commit -qm fixture
ref="$(git -C "$upstream" rev-parse HEAD)"
tree="$(git -C "$upstream" rev-parse HEAD:skills/third)"
jq -n \
	--arg source "$upstream" \
	--arg ref "$ref" \
	--arg tree "$tree" \
	'{version: 1, skills: {third: {source: "fixture/third", sourceUrl: $source, ref: $ref, skillPath: "skills/third/SKILL.md", gitTree: $tree}}}' \
	> "$third_source/agents/shared/third-party-skills.lock.json"

HOME="$third_home" DOTFILES_DIR="$third_source" "$third_source/scripts/restore-shared-skills.sh" >/dev/null
marker="$third_home/.agents/skills/third/.dotfiles-managed.json"
[[ -f "$marker" ]]
jq -e --arg ref "$ref" --arg tree "$tree" '.name == "third" and .ref == $ref and .gitTree == $tree' "$marker" >/dev/null
HOME="$third_home" DOTFILES_DIR="$third_source" "$third_source/scripts/restore-shared-skills.sh" --check >/dev/null

# A managed rerun replaces generated content without creating a backup.
HOME="$third_home" DOTFILES_DIR="$third_source" "$third_source/scripts/restore-shared-skills.sh" >/dev/null
[[ ! -d "$third_home/.local/share/dotfiles/migration-backups/skills" ]]

# Removing the marker turns the destination into unknown data; the next restore
# must preserve it before replacing it.
rm "$marker"
printf 'unknown local data\n' > "$third_home/.agents/skills/third/local.txt"
HOME="$third_home" DOTFILES_DIR="$third_source" "$third_source/scripts/restore-shared-skills.sh" >/dev/null
find "$third_home/.local/share/dotfiles/migration-backups/skills" -name local.txt -exec grep -l 'unknown local data' {} \; | grep -q .
printf 'PASS: third-party managed markers authorize replacement; unknown data is backed up\n'

printf 'OK: agent runtime migration fixtures passed\n'
