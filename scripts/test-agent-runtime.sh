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
		"$SOURCE/agents/shared/prompts" \
		"$SOURCE/agents/shared/scripts" \
		"$SOURCE/agents/shared/third-party-patches"
	cp "$ROOT/scripts/install-agents.sh" "$SOURCE/scripts/"
	cp "$ROOT/scripts/restore-shared-skills.sh" "$SOURCE/scripts/"
	cp "$ROOT/scripts/doctor.sh" "$SOURCE/scripts/"
	chmod +x "$SOURCE/scripts/install-agents.sh" "$SOURCE/scripts/restore-shared-skills.sh" "$SOURCE/scripts/doctor.sh"
	printf '# prompt\n' > "$SOURCE/agents/shared/prompts/example.md"
	printf '#!/bin/sh\nexit 0\n' > "$SOURCE/agents/shared/scripts/check-shared-skills.sh"
	chmod +x "$SOURCE/agents/shared/scripts/check-shared-skills.sh"
	printf '{"version":1,"skills":{}}\n' > "$SOURCE/agents/shared/third-party-skills.lock.json"
}

# Skills are authored in dotclaude; each fixture HOME gets its own ~/.claude/skills.
seed_dotclaude() {
	mkdir -p "$1/.claude/skills/example"
	printf '%s\n' '---' 'name: example' 'description: fixture' '---' > "$1/.claude/skills/example/SKILL.md"
}

must() {
	local message="$1"
	shift
	"$@" || { echo "FAIL: $message" >&2; exit 1; }
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
seed_dotclaude "$legacy_home"
printf 'old runtime\n' > "$legacy_source/agents/shared/skills/legacy/state.txt"
ln -s "$legacy_source/agents/shared" "$legacy_home/.agents"
run_first_party_install "$legacy_home" "$legacy_source"
HOME="$legacy_home" DOTFILES_DIR="$legacy_source" "$legacy_source/scripts/restore-shared-skills.sh" --check >/dev/null

[[ -d "$legacy_home/.agents" && ! -L "$legacy_home/.agents" ]]
[[ -L "$legacy_home/.agents/skills/example" ]]
must "example links to dotclaude" test "$(readlink "$legacy_home/.agents/skills/example")" = "$legacy_home/.claude/skills/example"
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
seed_dotclaude "$collision_home"
printf 'private skill state\n' > "$collision_home/.agents/skills/example/local.txt"
printf 'private prompts\n' > "$collision_home/.agents/prompts/local.txt"
run_first_party_install "$collision_home" "$collision_source"

[[ -L "$collision_home/.agents/skills/example" ]]
[[ -L "$collision_home/.agents/prompts" ]]
find "$collision_home/.local/share/dotfiles/migration-backups" -name local.txt -exec grep -l 'private skill state' {} \; | grep -q .
find "$collision_home/.local/share/dotfiles/migration-backups" -name local.txt -exec grep -l 'private prompts' {} \; | grep -q .
printf 'PASS: unmanaged runtime collisions are backed up before linking\n'

# dotclaude links: real skills only, lock names stay third-party, stale managed links retire.
setup_source dotclaude
dc_source="$SOURCE"
dc_home="$tmp/home-dotclaude"
dc_skills="$dc_home/.claude/skills"
seed_dotclaude "$dc_home"
mkdir -p "$dc_skills/claimed" "$dc_skills/no-skill-md" "$tmp/elsewhere/linked-in" "$dc_home/.agents/skills"
printf 'x\n' > "$dc_skills/claimed/SKILL.md"
ln -s "$tmp/elsewhere/linked-in" "$dc_skills/linked-in"
printf '{"version":1,"skills":{"claimed":{}}}\n' > "$dc_source/agents/shared/third-party-skills.lock.json"
ln -s "$dc_source/agents/shared/first-party-skills/old" "$dc_home/.agents/skills/old"
ln -s "$dc_skills/gone" "$dc_home/.agents/skills/gone"
ln -s "$tmp/not-ours" "$dc_home/.agents/skills/foreign"
dc_check() { HOME="$dc_home" DOTFILES_DIR="$dc_source" "$dc_source/scripts/restore-shared-skills.sh" --check-first-party >/dev/null 2>&1; }
must "check flags unlinked and stale entries before install" eval '! dc_check'
run_first_party_install "$dc_home" "$dc_source"
must "dotclaude skill linked" test "$(readlink "$dc_home/.agents/skills/example")" = "$dc_skills/example"
must "symlinked dotclaude entry not relinked" test ! -e "$dc_home/.agents/skills/linked-in" -a ! -L "$dc_home/.agents/skills/linked-in"
must "directory without SKILL.md not linked" test ! -L "$dc_home/.agents/skills/no-skill-md"
must "lock-claimed name left to third-party restore" test ! -L "$dc_home/.agents/skills/claimed"
must "legacy in-repo link pruned" test ! -L "$dc_home/.agents/skills/old"
must "removed dotclaude skill link pruned" test ! -L "$dc_home/.agents/skills/gone"
must "foreign dangling link untouched" test -L "$dc_home/.agents/skills/foreign"
must "check passes after install" dc_check
printf 'PASS: dotclaude skills link in; lock names and foreign links are left alone; stale links retire\n'

no_dc_home="$tmp/home-no-dotclaude"
mkdir -p "$no_dc_home"
must "install without ~/.claude succeeds" run_first_party_install "$no_dc_home" "$dc_source"
must "check without ~/.claude passes" env HOME="$no_dc_home" DOTFILES_DIR="$dc_source" "$dc_source/scripts/restore-shared-skills.sh" --check-first-party
printf 'PASS: a machine without dotclaude skips linking\n'

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
