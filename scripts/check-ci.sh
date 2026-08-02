#!/usr/bin/env bash
#MISE description="Run deterministic repository checks used by pull-request CI"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_check() {
	printf '\n==> %s\n' "$1"
	shift
	"$@"
}

run_check "public installer contract" "$ROOT/scripts/check-public-contract.sh"
run_check "public safety policy" "$ROOT/scripts/check-public-safety.sh"
run_check "public safety fixtures" "$ROOT/scripts/test-public-safety.sh"
run_check "repository completeness fixtures" "$ROOT/scripts/test-repository-completeness.sh"
run_check "agent runtime fixtures" "$ROOT/scripts/test-agent-runtime.sh"
run_check "x-ai-feed fixtures" python3 "$ROOT/agents/shared/first-party-skills/x-ai-feed/tests/test_feed.py"
if python3 -c 'import tomllib' >/dev/null 2>&1; then
	python311=(python3)
elif command -v uv >/dev/null 2>&1; then
	python311=(env "UV_CACHE_DIR=${UV_CACHE_DIR:-${TMPDIR:-/tmp}/dotfiles-check-ci-uv-cache}" uv run --script)
else
	echo "FAIL: mise pin updater tests require Python 3.11+ or uv" >&2
	exit 1
fi
run_check "mise pin updater fixtures" "${python311[@]}" "$ROOT/scripts/test-update-mise-pin.py"
run_check "Git write-boundary fixtures" "$ROOT/scripts/test-git-runtime.sh"
run_check "sync convergence fixtures" "$ROOT/scripts/test-sync.sh"
run_check "isolated doctor contract" "$ROOT/scripts/test-ci-doctor.sh"

printf '\nOK: deterministic repository CI contract passed\n'
