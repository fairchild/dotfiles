#!/usr/bin/env bash
#MISE description="Prove git config --global cannot mutate tracked public source"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

setup_source() {
	local name="$1"
	SOURCE="$tmp/source-$name"
	mkdir -p "$SOURCE/home" "$SOURCE/scripts"
	cp "$ROOT/scripts/install-git.sh" "$SOURCE/scripts/"
	chmod +x "$SOURCE/scripts/install-git.sh"
	cat > "$SOURCE/home/.gitconfig" <<'CFG'
[alias]
	fixture = status
CFG
	cat > "$SOURCE/home/.gitconfig.local.example" <<'CFG'
[user]
	name = Replace Me
	email = replace@example.invalid
CFG
}

run_install() {
	local fixture_home="$1" source="$2"
	HOME="$fixture_home" DOTFILES_DIR="$source" "$source/scripts/install-git.sh" >/dev/null
}

# Migrate the legacy write-through symlink, then prove a real global write only
# changes the private loader.
setup_source legacy
legacy_source="$SOURCE"
legacy_home="$tmp/home-legacy"
mkdir -p "$legacy_home"
cat > "$legacy_home/.gitconfig.local" <<'CFG'
[user]
	name = Fixture User
	email = fixture@example.com
CFG
ln -s "$legacy_source/home/.gitconfig" "$legacy_home/.gitconfig"
public_before="$(git hash-object "$legacy_source/home/.gitconfig")"
run_install "$legacy_home" "$legacy_source"

[[ -f "$legacy_home/.gitconfig" && ! -L "$legacy_home/.gitconfig" ]]
[[ "$(git config --file "$legacy_home/.gitconfig" --get-all include.path | grep -Fxc "$legacy_source/home/.gitconfig")" == "1" ]]
[[ "$(git config --file "$legacy_home/.gitconfig" --get-all include.path | grep -Fxc "$legacy_home/.gitconfig.local")" == "1" ]]
HOME="$legacy_home" GIT_CONFIG_NOSYSTEM=1 env -u GIT_CONFIG_GLOBAL git config --global safe.directory "$tmp/machine-specific"
[[ "$(git hash-object "$legacy_source/home/.gitconfig")" == "$public_before" ]]
[[ "$(git config --file "$legacy_home/.gitconfig" --get safe.directory)" == "$tmp/machine-specific" ]]
[[ "$(HOME="$legacy_home" GIT_CONFIG_NOSYSTEM=1 env -u GIT_CONFIG_GLOBAL git config user.email)" == "fixture@example.com" ]]
[[ "$(HOME="$legacy_home" GIT_CONFIG_NOSYSTEM=1 env -u GIT_CONFIG_GLOBAL git config alias.fixture)" == "status" ]]

run_install "$legacy_home" "$legacy_source"
[[ "$(git config --file "$legacy_home/.gitconfig" --get-all include.path | grep -Fxc "$legacy_source/home/.gitconfig")" == "1" ]]
[[ "$(git config --file "$legacy_home/.gitconfig" --get-all include.path | grep -Fxc "$legacy_home/.gitconfig.local")" == "1" ]]
[[ "$(git config --file "$legacy_home/.gitconfig" --get safe.directory)" == "$tmp/machine-specific" ]]
printf 'PASS: global writes stay private and repeated install preserves them\n'

# Preserve an existing private loader and seed its identity into the local
# overlay without removing unrelated private settings.
setup_source existing
existing_source="$SOURCE"
existing_home="$tmp/home-existing"
mkdir -p "$existing_home"
cat > "$existing_home/.gitconfig" <<'CFG'
[user]
	name = Existing User
	email = existing@example.com
[core]
	pager = false
CFG
run_install "$existing_home" "$existing_source"
[[ "$(git config --file "$existing_home/.gitconfig" --get core.pager)" == "false" ]]
[[ "$(git config --file "$existing_home/.gitconfig.local" --get user.email)" == "existing@example.com" ]]
printf 'PASS: existing private loader settings are preserved\n'

# An unexpected symlink is ambiguous and must be backed up before creating the
# private loader.
setup_source unexpected
unexpected_source="$SOURCE"
unexpected_home="$tmp/home-unexpected"
mkdir -p "$unexpected_home"
printf '[core]\n\tpager = cat\n' > "$unexpected_home/other-config"
ln -s "$unexpected_home/other-config" "$unexpected_home/.gitconfig"
run_install "$unexpected_home" "$unexpected_source"
[[ -f "$unexpected_home/.gitconfig" && ! -L "$unexpected_home/.gitconfig" ]]
find "$unexpected_home/.local/share/dotfiles/migration-backups" -type l -name 'gitconfig-symlink-*' -print -quit | grep -q .
printf 'PASS: unexpected symlink is preserved before migration\n'

printf 'OK: private Git loader fixtures passed\n'
