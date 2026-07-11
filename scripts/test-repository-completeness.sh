#!/usr/bin/env bash
#MISE description="Reproduce whitelist omission and broken-reference failures"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKER="$ROOT/scripts/check-repository-completeness.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
passed=0

make_repo() {
	local name="$1"
	REPO="$tmp/$name"
	mkdir -p "$REPO/scripts" "$REPO/docs"
	git -C "$REPO" init -q
	git -C "$REPO" config user.name fixture
	git -C "$REPO" config user.email fixture@example.com
	cat > "$REPO/.gitignore" <<'IGNORE'
*
!*/
!.gitignore
!.mise.toml
!README.md
!scripts/
!scripts/**
!docs/
!docs/**
*.local.*
IGNORE
	printf '# Fixture\n\n[Guide](docs/guide.md)\n' > "$REPO/README.md"
	printf '# Guide\n' > "$REPO/docs/guide.md"
	printf '#!/bin/sh\nexit 0\n' > "$REPO/scripts/task.sh"
	chmod +x "$REPO/scripts/task.sh"
	printf '[tasks.check]\nrun = "./scripts/task.sh"\n' > "$REPO/.mise.toml"
	cat > "$REPO/scripts/public-entrypoints.txt" <<'CONTRACT'
README.md|public readme
.mise.toml|task interface
docs/guide.md|guide
scripts/task.sh|task
CONTRACT
	git -C "$REPO" add .
	git -C "$REPO" commit -qm baseline
}

expect_pass() {
	local name="$1"
	shift
	if "$@" >/dev/null 2>&1; then
		printf 'PASS: %s\n' "$name"
		passed=$((passed + 1))
	else
		printf 'FAIL: expected pass: %s\n' "$name" >&2
		"$@" || true
		exit 1
	fi
}

expect_fail() {
	local name="$1"
	shift
	if "$@" >/dev/null 2>&1; then
		printf 'FAIL: expected rejection: %s\n' "$name" >&2
		exit 1
	else
		printf 'PASS: rejected %s\n' "$name"
		passed=$((passed + 1))
	fi
}

make_repo baseline
expect_pass "tracked entrypoints, relative links, and mise task" env DOTFILES_ENTRYPOINT_CONTRACT="$REPO/scripts/public-entrypoints.txt" "$CHECKER" --root "$REPO"

make_repo roadmap-omission
printf '\n[Roadmap](ROADMAP.md)\n' >> "$REPO/README.md"
printf '# Roadmap\n' > "$REPO/ROADMAP.md"
git -C "$REPO" add README.md
output="$(DOTFILES_ENTRYPOINT_CONTRACT="$REPO/scripts/public-entrypoints.txt" "$CHECKER" --root "$REPO" 2>&1 || true)"
grep -q 'ROADMAP.md' <<< "$output"
grep -q '.gitignore' <<< "$output"
printf 'PASS: reproduced ignored ROADMAP.md omission with responsible rule\n'
passed=$((passed + 1))

make_repo local-example-omission
printf 'home/.zshrc.local.example|public local overlay example\n' >> "$REPO/scripts/public-entrypoints.txt"
mkdir -p "$REPO/home"
printf '# local example\n' > "$REPO/home/.zshrc.local.example"
git -C "$REPO" add -f scripts/public-entrypoints.txt
expect_fail "ignored .local.example entrypoint" env DOTFILES_ENTRYPOINT_CONTRACT="$REPO/scripts/public-entrypoints.txt" "$CHECKER" --root "$REPO"

make_repo missing-link
printf '\n[Missing](docs/missing.md)\n' >> "$REPO/README.md"
git -C "$REPO" add README.md
expect_fail "missing relative documentation link" env DOTFILES_ENTRYPOINT_CONTRACT="$REPO/scripts/public-entrypoints.txt" "$CHECKER" --root "$REPO"

make_repo missing-task
printf '[tasks.check]\nrun = "./scripts/missing.sh"\n' > "$REPO/.mise.toml"
git -C "$REPO" add .mise.toml
expect_fail "missing mise task script" env DOTFILES_ENTRYPOINT_CONTRACT="$REPO/scripts/public-entrypoints.txt" "$CHECKER" --root "$REPO"

make_repo external-private
# shellcheck disable=SC2016 # The fixture intentionally documents a literal private path.
printf '\n[External](https://example.com)\n\nPrivate overlay: `~/.gitconfig.local`.\n' >> "$REPO/README.md"
git -C "$REPO" add README.md
expect_pass "external URL and private overlay prose are ignored" env DOTFILES_ENTRYPOINT_CONTRACT="$REPO/scripts/public-entrypoints.txt" "$CHECKER" --root "$REPO"

printf 'OK: %s repository-completeness fixture cases passed\n' "$passed"
