#!/usr/bin/env bash
#MISE description="Verify public entrypoints, required paths, and fixture bootstrap"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLIC_INSTALL_URL="https://raw.githubusercontent.com/fairchild/dotfiles/master/install.sh"
network=0

case "${1:-}" in
    "") ;;
    --network) network=1 ;;
    *) echo "usage: $0 [--network]" >&2; exit 2 ;;
esac

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

	required_paths=(
		.gitleaks.toml
    .gitignore
    .mise.toml
    LICENSE
    README.md
    ROADMAP.md
		docs/policy.md
		docs/public-safety.md
		docs/source-runtime-contract.md
		docs/sync.md
    install.sh
    install/pins.toml
		scripts/check-public-contract.sh
		scripts/check-public-safety.sh
    scripts/doctor.sh
    scripts/install-agents.sh
    scripts/install-brew.sh
    scripts/install-git.sh
    scripts/install-zsh.sh
		scripts/restore-shared-skills.sh
		scripts/sync.sh
		scripts/test-install.sh
		scripts/test-agent-runtime.sh
		scripts/test-git-runtime.sh
		scripts/test-sync.sh
		scripts/test-public-safety.sh
	)

for path in "${required_paths[@]}"; do
    [[ -e "$ROOT/$path" ]] || fail "required public path is absent: $path"
    git -C "$ROOT" ls-files --error-unmatch "$path" >/dev/null 2>&1 \
		|| fail "required public path is not tracked: $path"
done

if rg -n 'raw\.githubusercontent\.com/fairchild/dotfiles/main' \
    "$ROOT/README.md" "$ROOT/install.sh" "$ROOT/docs" >/dev/null; then
    fail "public documentation still references the nonexistent main branch"
fi

rg -F "$PUBLIC_INSTALL_URL" "$ROOT/README.md" >/dev/null \
    || fail "README does not contain the canonical public install URL"
rg -F 'raw.githubusercontent.com/fairchild/dotfiles/master' "$ROOT/install.sh" >/dev/null \
    || fail "install.sh does not default to the canonical master raw base"

sh -n "$ROOT/install.sh"
"$ROOT/scripts/test-install.sh"

if (( network )); then
    curl -fsSL --max-time 30 "$PUBLIC_INSTALL_URL" >/dev/null \
		|| fail "published installer URL did not resolve: $PUBLIC_INSTALL_URL"
    printf 'OK: published installer URL resolves\n'
fi

printf 'OK: public repository contract verified\n'
