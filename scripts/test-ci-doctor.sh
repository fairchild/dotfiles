#!/usr/bin/env bash
#MISE description="Exercise the CI-safe doctor contract in an isolated HOME"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

fixture_home="$tmp/home"
fixture_source="$tmp/source"
mkdir -p "$fixture_home" "$fixture_source"

# Build a clean repository from the current Git-visible working tree. This lets
# contributors reproduce CI before committing while keeping doctor's real
# source-cleanliness check intact.
while IFS= read -r -d '' path; do
	mkdir -p "$fixture_source/$(dirname "$path")"
	cp -pR "$ROOT/$path" "$fixture_source/$path"
done < <(git -C "$ROOT" ls-files --cached --others --exclude-standard -z)
git -C "$fixture_source" init -q
git -C "$fixture_source" config user.name fixture
git -C "$fixture_source" config user.email fixture@example.com
git -C "$fixture_source" add .
git -C "$fixture_source" commit -qm fixture

export HOME="$fixture_home"
export DOTFILES_DIR="$fixture_source"
export DOTFILES_SKIP_THIRD_PARTY_SKILLS=1
export DOTFILES_EXPECTED_GIT_REF="$(git -C "$fixture_source" rev-parse HEAD)"

"$fixture_source/scripts/install-zsh.sh"
"$fixture_source/scripts/install-git.sh"
"$fixture_source/scripts/install-agents.sh"
"$fixture_source/scripts/doctor.sh" --core

printf 'OK: isolated CI doctor contract passed\n'
