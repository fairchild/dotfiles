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
run_check "Git write-boundary fixtures" "$ROOT/scripts/test-git-runtime.sh"
run_check "sync convergence fixtures" "$ROOT/scripts/test-sync.sh"
run_check "isolated doctor contract" "$ROOT/scripts/test-ci-doctor.sh"

printf '\nOK: deterministic repository CI contract passed\n'
